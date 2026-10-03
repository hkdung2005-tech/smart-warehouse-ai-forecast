# API Contract (SCRUM-12)

Phiên bản: 1.2 (đã sửa theo Worker của Bảo, SCRUM-18)
Người phụ trách: Chấn

Base URL (chạy local): `http://localhost:8000`
Định dạng: JSON, UTF-8. Header: `Content-Type: application/json`.

## 1. Tổng quan luồng

1. Client gọi `POST /jobs` gửi yêu cầu.
2. API lưu job vào PostgreSQL (`pending`), **commit xong** rồi đẩy job vào Main queue (`jobs`) của RabbitMQ và **trả `job_id` ngay**, không chờ Gemini.
3. Worker lấy job từ `jobs`. Tốc độ được giới hạn bằng `prefetch_count=1` và bộ giới hạn 10 lần gọi Gemini mỗi giây trên mỗi tiến trình Worker (rate-limit).
4. Worker gọi Gemini (hoặc Mock Gemini) rồi cập nhật trạng thái, kết quả vào PostgreSQL.
5. Lỗi tạm thời (429, 5xx, timeout): Worker đưa job vào Retry queue theo exponential backoff 1s, 2s, 4s. Hết thời gian chờ, job tự quay lại `jobs`.
6. Đã retry 3 lần mà vẫn lỗi tạm thời: **Worker đẩy job vào DLQ** (`jobs.dlq`) và đánh dấu job `failed`.
7. Client gọi `GET /jobs/{job_id}` để xem trạng thái và kết quả (API đọc từ PostgreSQL).

## 2. Trạng thái job (`status`)

| Giá trị | Ý nghĩa |
| --- | --- |
| `pending` | Đã nhận, đang chờ trong Main queue |
| `processing` | Worker đang gọi Gemini |
| `retrying` | Gọi lỗi tạm thời, đang chờ backoff ở Retry queue. `error_message` giữ lỗi gần nhất |
| `completed` | Có kết quả từ Gemini |
| `failed` | Thất bại, có 3 trường hợp: (a) lỗi vĩnh viễn, không vào DLQ; (b) quá 3 lần retry, đã vào DLQ; (c) API không publish được job vào queue |

## 3. Endpoints

### 3.1 `GET /health`

Kiểm tra API còn sống.

Response `200 OK`:
```json
{ "status": "ok" }
```

### 3.2 `POST /jobs`

Tạo job mới.

Request body:
```json
{
  "payload": "Dự báo lượng hàng tồn kho cần nhập cho sản phẩm A"
}
```

| Trường | Kiểu | Bắt buộc | Mô tả |
| --- | --- | --- | --- |
| `payload` | string | Có | Nội dung gửi cho Gemini, không được rỗng |

Response `202 Accepted`:
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "pending",
  "created_at": "2026-10-02T09:15:30Z"
}
```

Lỗi:
- `422 Unprocessable Entity`: thiếu `payload` hoặc `payload` rỗng.
- `503 Service Unavailable`: không kết nối được RabbitMQ hoặc PostgreSQL.

Quy tắc phía API:
- Lưu job vào DB và **commit** trước khi publish. Worker không tìm thấy job trong DB sẽ trả message về queue và thử lại mãi.
- Publish lỗi sau khi đã lưu DB: API chuyển job sang `failed` (`error_message`: "Publish to queue failed"), ghi event `publish_failed` vào `job_logs` rồi trả `503`.

### 3.3 `GET /jobs/{job_id}`

Xem trạng thái và kết quả của job. Đọc trực tiếp từ PostgreSQL.

Response `200 OK` (đang retry):
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "retrying",
  "result": null,
  "error_message": "Gemini returned HTTP 429",
  "retry_count": 2,
  "created_at": "2026-10-02T09:15:30Z",
  "updated_at": "2026-10-02T09:15:41Z"
}
```

Response `200 OK` (hoàn thành):
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "completed",
  "result": "Nội dung Gemini trả về",
  "error_message": null,
  "retry_count": 1,
  "created_at": "2026-10-02T09:15:30Z",
  "updated_at": "2026-10-02T09:15:45Z"
}
```

Response `200 OK` (thất bại, quá 3 lần retry, đã vào DLQ):
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "failed",
  "result": null,
  "error_message": "Gemini returned HTTP 429",
  "retry_count": 3,
  "created_at": "2026-10-02T09:15:30Z",
  "updated_at": "2026-10-02T09:15:52Z"
}
```

Lưu ý: `error_message` là lỗi gần nhất Worker ghi nhận (nội dung phản hồi của Gemini, hoặc mô tả lỗi kết nối). Khi job sang `processing` hoặc `completed`, Worker xóa `error_message` (về null).

Lỗi:
- `404 Not Found`: không có job với `job_id` này.
- `422 Unprocessable Entity`: `job_id` không đúng định dạng UUID.

## 4. Định dạng lỗi

Dùng mặc định của FastAPI:
```json
{ "detail": "Job not found" }
```

## 5. RabbitMQ

### 5.1 Các queue

| Queue | Mục đích |
| --- | --- |
| `jobs` | Main queue, API gửi vào, Worker đọc |
| `jobs.retry.1s` | Giữ job 1 giây (retry lần 1), hết thời gian tự chuyển về `jobs` |
| `jobs.retry.2s` | Giữ job 2 giây (retry lần 2), hết thời gian tự chuyển về `jobs` |
| `jobs.retry.4s` | Giữ job 4 giây (retry lần 3), hết thời gian tự chuyển về `jobs` |
| `jobs.dlq` | Dead Letter Queue, Worker đẩy vào khi quá số lần retry hoặc message sai định dạng |

Các queue đều `durable`. Worker tự khai báo khi khởi động.

**Xử lý DLQ (giai đoạn giữa kỳ):** admin xem các message trong `jobs.dlq` thủ công qua RabbitMQ Management UI tại `http://localhost:15672`. Chưa có API hay cơ chế tự động đưa job từ DLQ quay lại `jobs`.

### 5.2 Message API gửi vào `jobs`

Gửi qua default exchange, routing key `jobs`, `delivery_mode=2` (persistent), dạng JSON:
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "payload": "Dự báo lượng hàng tồn kho cần nhập cho sản phẩm A",
  "retry_count": 0
}
```

- `job_id` và `payload` phải là chuỗi không rỗng. Thiếu hoặc sai kiểu thì Worker đẩy message vào DLQ và không cập nhật DB.
- Nếu API tự khai báo queue `jobs`, phải dùng `durable=True` và **không** thêm tham số nào khác. Khai báo khác Worker sẽ báo lỗi `PRECONDITION_FAILED`.
- Tên queue lấy từ biến môi trường `MAIN_QUEUE` (mặc định `jobs`), API và Worker phải dùng cùng giá trị.

## 6. Quy tắc xử lý của Worker

| Tình huống | Xử lý | `status` / event ghi vào `job_logs` |
| --- | --- | --- |
| Gọi thành công | Lưu `result`, ack message | `completed` / `completed` |
| Lỗi `429`, `5xx`, timeout, lỗi kết nối, và chưa quá 3 lần retry | Tăng `retry_count`, đẩy vào `jobs.retry.1s` / `2s` / `4s` theo lần retry | `retrying` / `retry_scheduled` |
| Lỗi tạm thời và đã retry đủ 3 lần | Worker đẩy message vào `jobs.dlq` | `failed` / `moved_to_dlq` |
| Mã HTTP khác (400, 401, 403, 404...), hoặc phản hồi 200 nhưng không phải JSON có `result` dạng chuỗi | Lỗi vĩnh viễn: không retry, **không** vào DLQ | `failed` / `failed` |
| Message sai định dạng (không phải JSON, thiếu `job_id` hoặc `payload`) | Đẩy vào `jobs.dlq`, ack, không cập nhật DB | Không ghi |

`MAX_RETRIES=3` nghĩa là một job được gọi Gemini tối đa 4 lần (1 lần đầu + 3 lần retry). Job `failed` do quá retry có `retry_count = 3`.

**Giao diện Worker và Gemini client:**
- Hàm `generate(payload: str) -> str` trả về text kết quả, timeout 60 giây.
- Khi lỗi, raise `GeminiError(message, status_code)`. `status_code` là `None` nếu timeout hoặc lỗi kết nối.
- Endpoint Gemini hiện được gọi theo định dạng riêng: `POST {GEMINI_API_URL}` (mặc định `http://localhost:9000/generate`), body `{"payload": "..."}`, trả `{"result": "..."}`. Mock Gemini phải theo đúng định dạng này và trả được các mã `200`, `429`, `500`.
- Định dạng trên không phải định dạng REST thật của Gemini API. Muốn gọi Gemini thật cần thêm lớp chuyển đổi (Đại phụ trách).

**Rate-limit:** `prefetch_count=1` (mỗi tiến trình chỉ giữ 1 job chưa ack) cộng với bộ giới hạn `RATE_LIMIT_PER_SECOND=10` lần gọi mỗi giây trên mỗi tiến trình. Chạy nhiều Worker thì tổng tốc độ tăng theo số Worker, cần bộ giới hạn dùng chung nếu muốn giới hạn tổng.

**Tránh xử lý trùng:** trước khi xử lý, Worker đọc `status` trong DB. Job đã `completed` hoặc `failed` thì ack và bỏ qua.

**Thứ tự ack:** Worker chỉ ack sau khi đã cập nhật DB xong và publish retry/DLQ thành công (có publisher confirm). Lỗi DB hoặc mạng thì trả message về queue.

**Biến môi trường của Worker:**

| Biến | Mặc định |
| --- | --- |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/warehouse` |
| `GEMINI_API_URL` | `http://localhost:9000/generate` |
| `GEMINI_API_KEY` | để trống |
| `MAIN_QUEUE` | `jobs` |
| `DLQ` | `jobs.dlq` |
| `MAX_RETRIES` | `3` |
| `RATE_LIMIT_PER_SECOND` | `10` |
| `PREFETCH_COUNT` | `1` |

## 7. Database

Hai bảng `jobs` và `job_logs` phải tồn tại trước khi chạy API và Worker (tạo bằng file SQL khởi tạo trong Docker Compose).

### 7.1 Bảng `jobs`

| Cột | Kiểu | Ghi chú |
| --- | --- | --- |
| `job_id` | UUID | Khóa chính |
| `payload` | TEXT | Nội dung gửi Gemini |
| `status` | VARCHAR | Một trong 5 giá trị ở mục 2 |
| `result` | TEXT | Null khi chưa có kết quả |
| `error_message` | TEXT | Null khi không lỗi |
| `retry_count` | INTEGER | Mặc định 0 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | Worker cập nhật mỗi lần đổi trạng thái |

### 7.2 Bảng `job_logs`

Quan hệ: 1 `jobs` có nhiều `job_logs` (`has_log`).

| Cột | Kiểu | Ghi chú |
| --- | --- | --- |
| `log_id` | SERIAL / BIGSERIAL | Khóa chính, **tự tăng** (Worker không truyền giá trị này khi insert) |
| `job_id` | UUID | Khóa ngoại tới `jobs.job_id` |
| `event` | VARCHAR | Tên sự kiện, xem bên dưới |
| `created_at` | TIMESTAMP | |

Các giá trị `event`:
- API ghi: `created`, `published`, `publish_failed`.
- Worker ghi: `processing`, `completed`, `retry_scheduled`, `moved_to_dlq`, `failed`.

Job thất bại do quá số lần retry ghi `moved_to_dlq` (không ghi thêm `failed`). Event `failed` chỉ dành cho lỗi vĩnh viễn do Worker ghi nhận. Job không publish được vào queue (lỗi ở API) có `status = failed` nhưng ghi event `publish_failed`.

## 8. Các điểm cần nhóm xác nhận

- **Đoàn:** file SQL khởi tạo hai bảng trong Docker Compose (kể cả `log_id` tự tăng), truyền đủ biến môi trường cho Worker. RabbitMQ dùng image có management (ví dụ `rabbitmq:3-management`) và mở cổng `15672` để admin xem DLQ.
- **Đại:** Mock Gemini theo định dạng ở mục 6 (`POST /generate`, trả `{"result": "..."}`, hỗ trợ mã 200/429/500), và hướng xử lý khi gọi Gemini thật.
- **Chấn:** API commit DB trước khi publish, publish vào `jobs` với `durable`, persistent, đúng định dạng message ở mục 5.2.
- **Dung:** ERD ghi rõ khóa ngoại `job_id` trong `job_logs` và 5 giá trị `status`.
