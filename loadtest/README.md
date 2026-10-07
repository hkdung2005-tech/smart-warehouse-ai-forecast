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
- **Dữ liệu test**: Payload được đính kèm `id=<uuid>` (dùng UUID đầy đủ) để đảm bảo Mock Gemini đếm chính xác số lượng request, kể cả khi chạy hàng chục nghìn request.
- **Tự động Reset Mock**: Script tự động gọi API `POST http://localhost:9000/admin/reset` trước mỗi lần chạy test thông qua sự kiện `test_start` của Locust.
- **Ghi chú về Latency**: Latency ghi nhận bởi Locust chỉ đo thời gian phản hồi của API `POST /jobs` (nhận mã 202 Accepted). Nó **KHÔNG** đại diện cho thời gian Worker xử lý xong job. Để lấy thời gian xử lý thực tế, cần tính chênh lệch giữa `updated_at` và `created_at` trong DB.

## 3. Lựa chọn mức tải

Theo yêu cầu của hệ thống (Worker giới hạn tối đa 10 lần gọi Gemini/giây):
- **Tải 1x (3 users)**: Đại diện cho mức tải bình thường. 3 users bắn request (khoảng 3 request/s mỗi user) sẽ sinh ra tổng cộng khoảng 9-10 request/s, xấp xỉ ngưỡng của Worker. Ở mức này, queue không bị phình quá to và hệ thống xử lý nhịp nhàng.
- **Tải 10x (30 users)**: Đại diện cho mức ép tải hệ thống gấp 10 lần (khoảng 90-100 request/s). Lúc này API vẫn tiếp nhận bình thường (trả 202) nhưng queue RabbitMQ sẽ phình to ra và Worker sẽ phải cật lực xử lý ở mức tối đa 10 job/giây.

## 4. Cách chạy test và lấy báo cáo (Headless)

Theo yêu cầu của TC-NFR-01, cần xuất báo cáo CSV và HTML cho từng mức tải mà không cần thao tác thủ công trên giao diện web.

**Chạy tải 1x (3 users) trong 1 phút:**
```bash
locust -f locustfile.py --host=http://localhost:8000 --headless -u 3 -r 1 -t 1m --csv=report_1x --html=report_1x.html
```

**Chạy tải 10x (30 users) trong 1 phút:**
```bash
locust -f locustfile.py --host=http://localhost:8000 --headless -u 30 -r 5 -t 1m --csv=report_10x --html=report_10x.html
```

Các file báo cáo (`report_1x.html`, `report_1x_stats.csv`, v.v.) sẽ được tự động tạo ra trong cùng thư mục `loadtest`. Bạn có thể dùng các file này để đọc Throughput (Requests/s), Error rate (Failures/s) và Latency.

## 5. Đối chiếu kết quả với Database

⚠️ **Quan trọng:** Để số liệu đếm của lệnh SQL không bị nhầm lẫn giữa các lần chạy, bạn **phải xóa sạch dữ liệu cũ** trong database trước khi bắt đầu bài test tiếp theo (ví dụ: chuyển từ 1x sang 10x):
```bash
docker compose exec postgres psql -U postgres -d warehouse -c "TRUNCATE TABLE job_logs, jobs;"
```

Sau khi chạy xong bài test bằng Locust, hãy chờ một khoảng thời gian cho đến khi Worker xử lý hết hàng đợi (vì Worker bị giới hạn 10 request/giây). Sau đó chạy lệnh sau để kiểm tra dữ liệu:

```bash
docker compose exec postgres psql -U postgres -d warehouse -c "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```

Số lượng `completed` + `failed` thu được từ câu lệnh trên phải bằng đúng số `Requests` thành công ghi nhận trong file báo cáo CSV của Locust. Không được còn job nào bị kẹt ở trạng thái `pending`, `processing` hay `retrying`.
