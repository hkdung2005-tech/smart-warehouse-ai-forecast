# API Contract (SCRUM-12)

Phiên bản: 1.0 (đã đối chiếu với sơ đồ kiến trúc SCRUM-11 và ERD SCRUM-10)
Người phụ trách: Chấn

Base URL (chạy local): `http://localhost:8000`
Định dạng: JSON, UTF-8. Header: `Content-Type: application/json`.

## 1. Tổng quan luồng

1. Client gọi `POST /jobs` gửi yêu cầu.
2. API lưu job vào PostgreSQL (`pending`), đẩy job vào Main queue của RabbitMQ rồi **trả `job_id` ngay**, không chờ Gemini.
3. Worker lấy job từ Main queue (có `prefetch` để giới hạn tốc độ), gọi Gemini (hoặc Mock Gemini) và cập nhật trạng thái job vào PostgreSQL.
4. Lỗi tạm thời (429, 5xx, timeout) thì job vào Retry queue, hết thời gian backoff quay lại Main queue. Quá số lần retry thì vào DLQ.
5. Client gọi `GET /jobs/{job_id}` để xem trạng thái và kết quả.

## 2. Trạng thái job (`status`)

| Giá trị | Ý nghĩa |
| --- | --- |
| `pending` | Đã nhận, đang chờ trong Main queue |
| `processing` | Worker đang gọi Gemini |
| `retrying` | Gọi lỗi tạm thời, đang chờ backoff ở Retry queue |
| `completed` | Có kết quả từ Gemini |
| `failed` | Lỗi vĩnh viễn hoặc quá số lần retry (job đã vào DLQ nếu do quá số lần retry) |

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

Quy tắc khi publish lỗi: nếu đã lưu DB nhưng publish vào RabbitMQ thất bại, API chuyển job sang `failed` (`error_message`: "Publish to queue failed"), ghi log vào `job_logs` rồi trả `503`. Không để job nằm `pending` mãi.

### 3.3 `GET /jobs/{job_id}`

Xem trạng thái và kết quả của job. Đọc trực tiếp từ PostgreSQL.

Response `200 OK` (đang retry):
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "retrying",
  "result": null,
  "error_message": null,
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

Response `200 OK` (thất bại):
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "status": "failed",
  "result": null,
  "error_message": "Quá số lần retry: 429 Too Many Requests",
  "retry_count": 5,
  "created_at": "2026-10-02T09:15:30Z",
  "updated_at": "2026-10-02T09:16:20Z"
}
```

Lỗi:
- `404 Not Found`: không có job với `job_id` này.
- `422 Unprocessable Entity`: `job_id` không đúng định dạng UUID.

## 4. Định dạng lỗi

Dùng mặc định của FastAPI:
```json
{ "detail": "Job not found" }
```

## 5. Message trong RabbitMQ (giữa API và Worker)

Message API gửi vào Main queue, dạng JSON:
```json
{
  "job_id": "3f2b8c1e-7a44-4d0e-9a51-2b6f0c9d1e77",
  "payload": "Dự báo lượng hàng tồn kho cần nhập cho sản phẩm A",
  "retry_count": 0
}
```

Worker tăng `retry_count` mỗi lần đưa job vào Retry queue.

## 6. Quy tắc xử lý của Worker

**Phân loại lỗi khi gọi Gemini:**

| Lỗi | Xử lý |
| --- | --- |
| `429`, `5xx`, timeout | Retry: đưa vào Retry queue, chờ backoff, tăng `retry_count` |
| `400`, `401`, `403`, `404` | Lỗi vĩnh viễn: chuyển thẳng `failed`, không retry |
| Vượt số lần retry tối đa | Chuyển `failed`, đẩy job vào DLQ |

**Giao diện Worker và Gemini client (do Đại viết):**
- Hàm `generate(payload: str) -> str` trả về text kết quả.
- Khi lỗi, raise exception có thuộc tính `status_code` (và `None` nếu là timeout). Worker dựa vào đó để chọn retry hay `failed`.
- Mock Gemini phải trả được các mã `200`, `429`, `500` để test retry và DLQ.

**Tránh xử lý trùng:** RabbitMQ có thể giao trùng message. Trước khi xử lý, Worker đọc `status` trong DB; nếu job đã `completed` hoặc `failed` thì bỏ qua và ack message.

**Thứ tự ack:** chỉ ack message sau khi đã cập nhật DB xong.

## 7. Database

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
| `updated_at` | TIMESTAMP | |

### 7.2 Bảng `job_logs`

Quan hệ: 1 `jobs` có nhiều `job_logs` (`has_log`).

| Cột | Kiểu | Ghi chú |
| --- | --- | --- |
| `log_id` | SERIAL / BIGINT | Khóa chính |
| `job_id` | UUID | Khóa ngoại tới `jobs.job_id` |
| `event` | VARCHAR | Tên sự kiện, xem bên dưới |
| `created_at` | TIMESTAMP | |

Các giá trị `event` đề xuất: `created`, `published`, `processing`, `retry_scheduled`, `completed`, `failed`, `moved_to_dlq`.

## 8. Các điểm cần nhóm xác nhận

- **Dung:** ERD cần thể hiện khóa ngoại `job_id` trong `job_logs`, và ghi rõ 5 giá trị của `status`. Hiện hình ERD chưa có.
- **Bảo:** tên queue (Main, Retry, DLQ), số lần retry tối đa, thời gian backoff. Cơ chế "quá số lần retry thì vào DLQ" do Worker đẩy hay do Retry queue chuyển, để sơ đồ kiến trúc vẽ đúng.
- **Đại:** giao diện `generate()` và các mã lỗi mà Mock Gemini trả về (mục 6).
