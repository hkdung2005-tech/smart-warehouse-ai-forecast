# Load test Locust (SCRUM-28)

Kịch bản Load Test dùng Locust để kiểm thử khả năng chịu tải của API và Worker (US-05).

## 1. Cài đặt

Yêu cầu: Đã cài đặt Python 3.9+
Chạy lệnh cài đặt Locust:

```bash
pip install locust
```

## 2. Kịch bản test (locustfile.py)

- **Mục tiêu**: Bắn liên tục request `POST /jobs`.
- **Dữ liệu test**: Payload được đính kèm `id=<uuid>` theo yêu cầu của Mock Gemini (`gemini/README.md`) để đếm chính xác số lượng request.
- **Không gửi tag `[mock:timeout]`** trong kịch bản này (như yêu cầu tại TC-NFR-01).

## 3. Cách chạy test

1. Đảm bảo toàn bộ hệ thống đang chạy (`docker compose up -d`).
2. Mở terminal tại thư mục `loadtest`, chạy lệnh:
   ```bash
   locust -f locustfile.py --host=http://localhost:8000
   ```
3. Mở trình duyệt truy cập Locust UI tại: `http://localhost:8089`.
4. Nhập cấu hình chạy test:
   - **Number of users**: `10` (cho mức 1x) hoặc `100` (cho mức 10x).
   - **Spawn rate**: `5` (số user tăng lên mỗi giây).
5. Nhấn **Start swarming** để bắt đầu test.

## 4. Cách lấy số liệu (TC-NFR-01)

Theo yêu cầu của TC-NFR-01:
1. Ghi lại số **Requests/s** (Throughput), **Failures/s** (Error rate) và **Average Response Time** (Latency) trên giao diện Locust.
2. Kiểm tra lại số lượng message đã được xử lý thành công trong DB (cần phải bằng số request trả về 202 trên Locust):
   ```bash
   docker compose exec postgres psql -U postgres -d warehouse -c "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
   ```
   Số lượng `completed` + `failed` phải bằng đúng số `Requests` thành công ghi nhận bởi Locust, và không còn job nào bị kẹt ở `pending`, `processing` hay `retrying` sau khi xử lý xong queue.
3. Trước khi chạy mức tải mới (ví dụ từ 1x lên 10x), **phải reset lại Mock Gemini**:
   ```bash
   curl -X POST http://localhost:9000/admin/reset
   ```
