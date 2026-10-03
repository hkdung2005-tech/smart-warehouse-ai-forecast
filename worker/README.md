# Worker consumer (Bảo)

Worker nhận job từ RabbitMQ, gọi endpoint tương thích Gemini và lưu các thay đổi trạng thái vào PostgreSQL. Khi khởi động, worker tự khai báo các queue bền vững. API có thể gửi message qua default exchange với routing key `jobs`.

## Queue và chính sách retry

| Queue | Mục đích |
| --- | --- |
| `jobs` | Queue chính, worker đọc message từ đây |
| `jobs.retry.1s` | Giữ lần retry thứ nhất trong 1 giây, sau đó chuyển lại vào `jobs` |
| `jobs.retry.2s` | Giữ lần retry thứ hai trong 2 giây, sau đó chuyển lại vào `jobs` |
| `jobs.retry.4s` | Giữ lần retry thứ ba trong 4 giây, sau đó chuyển lại vào `jobs` |
| `jobs.dlq` | Lưu các lỗi tạm thời vẫn thất bại sau ba lần retry |

Worker retry khi gặp lỗi `429`, `5xx` hoặc timeout. Các lỗi HTTP khác là lỗi vĩnh viễn: job được chuyển sang trạng thái `failed` mà không đưa vào DLQ. Sau ba lần retry, nếu vẫn gặp lỗi có thể retry, worker gửi message vào DLQ kèm header `x-error` và `x-retry-count`. Queue và message đều được lưu bền vững trong RabbitMQ. Consumer dùng manual acknowledgement và publisher confirm; worker chỉ ack sau khi cập nhật DB và publish retry/DLQ thành công.

Rate limiter mặc định cho phép tối đa 10 lần gọi Gemini mỗi giây trên mỗi tiến trình worker. `prefetch_count=1` giới hạn mỗi tiến trình chỉ nhận một job chưa ack tại một thời điểm. Nếu chạy nhiều worker replica, cần cấu hình rate limiter dùng chung để giới hạn tổng số request giữa các replica.

## Cấu hình

| Biến môi trường | Giá trị mặc định | Ý nghĩa |
| --- | --- | --- |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/%2F` | URL kết nối AMQP |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/warehouse` | URL kết nối PostgreSQL |
| `GEMINI_API_URL` | `http://localhost:9000/generate` | Endpoint Gemini hoặc mock |
| `GEMINI_API_KEY` | để trống | Bearer token, không bắt buộc |
| `MAIN_QUEUE` | `jobs` | Tên queue chính, phải trùng với cấu hình của API |
| `DLQ` | `jobs.dlq` | Tên dead letter queue |
| `MAX_RETRIES` | `3` | Số lần retry sau lần gọi đầu tiên |
| `RATE_LIMIT_PER_SECOND` | `10` | Số lần gọi tối đa mỗi giây trên một tiến trình |
| `PREFETCH_COUNT` | `1` | Số message RabbitMQ worker nhận trước khi ack |

Endpoint Gemini nhận request `POST {"payload":"..."}` và cần trả về `{"result":"..."}`. Worker phân loại lỗi theo mã HTTP; timeout và lỗi kết nối không có mã HTTP nên được xem là lỗi có thể retry.

PostgreSQL cần có hai bảng `jobs` và `job_logs` theo mô tả trong [`docs/api-contract.md`](../docs/api-contract.md). Worker cập nhật các cột `status`, `result`, `error_message`, `retry_count`, `updated_at` và thêm sự kiện tương ứng vào `job_logs`.

## Chạy tại máy local

Từ thư mục gốc của repository, khởi động RabbitMQ, PostgreSQL và Gemini mock trước, sau đó chạy worker:

```powershell
python -m venv worker/.venv
worker/.venv/Scripts/python -m pip install -r worker/requirements.txt
$env:RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/warehouse"
$env:GEMINI_API_URL = "http://localhost:9000/generate"
python -m worker
```

Để build container từ thư mục gốc repository:

```powershell
docker build -f worker/Dockerfile -t smart-warehouse-worker .
```

Khi chạy container, truyền các biến môi trường cấu hình ở trên. Cấu hình Docker Compose ở thư mục gốc hiện chưa được bổ sung.
