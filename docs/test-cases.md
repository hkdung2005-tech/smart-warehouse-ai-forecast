# Tài liệu Test Case

Smart Warehouse – AI Forecast (Giai đoạn 1: Prototype RabbitMQ)

- **Mã ticket:** SCRUM-25
- **Người soạn:** Dung (PM/BA)
- **Ngày soạn:** 04/10/2026
- **Phiên bản:** 1.0 (bản nháp)
- **Căn cứ:** SRS (FR-01 đến FR-08, NFR-01 đến NFR-05), User Stories (US-01 đến US-06), API Contract v1.3

## 1. Phạm vi và cách đọc

- Tài liệu gồm 24 test case, chia theo nhóm chức năng. Mỗi test case ghi rõ yêu cầu (FR/NFR/US) mà nó kiểm tra.
- Cột "Kết quả thực tế" và "Trạng thái" (Pass/Fail) để trống, người phụ trách module điền khi chạy test. Lỗi phát hiện được ghi thành ticket Bug trên Jira.
- Các test case dùng Mock Gemini cần Mock hỗ trợ trả 200, 429, 500, 400 và phản hồi chậm (SCRUM-21).
- Mức ưu tiên: High = chức năng cốt lõi; Medium = quan trọng; Low = mở rộng hoặc thực hiện thủ công.

## 2. Danh sách test case

### 2.1 API tạo job (POST /jobs) và kiểm tra hệ thống

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-API-01 | FR-01, US-01, NFR-02 | Gửi yêu cầu hợp lệ | API, RabbitMQ, PostgreSQL đang chạy | 1. Mở /docs<br>2. POST /jobs → Try it out<br>3. Nhập body, bấm Execute | {"payload":"Dự báo lượng hàng tồn kho cần nhập cho sản phẩm A"} | HTTP 202. Body có job_id (UUID), status = "pending", created_at dạng ...Z. Thời gian phản hồi dưới 1 giây. | High |  |  |
| TC-API-02 | FR-01 | Gửi payload rỗng | API đang chạy | 1. POST /jobs<br>2. Nhập body, bấm Execute | {"payload":""} | HTTP 422. Thông báo cho biết payload không được rỗng. Không tạo job mới. | High |  |  |
| TC-API-03 | FR-01 | Gửi thiếu trường payload | API đang chạy | 1. POST /jobs<br>2. Nhập body, bấm Execute | {} | HTTP 422 (thiếu trường bắt buộc payload). | High |  |  |
| TC-API-04 | FR-01 | Gửi payload sai kiểu dữ liệu | API đang chạy | 1. POST /jobs<br>2. Nhập body, bấm Execute | {"payload":123} | HTTP 422 (payload phải là chuỗi). | Medium |  |  |
| TC-API-05 | FR-01, FR-08 | Job được lưu DB và đưa vào queue | Tắt Worker để message không bị lấy đi | 1. POST /jobs hợp lệ, ghi lại job_id<br>2. Mở RabbitMQ UI (cổng 15672) → Queues → jobs<br>3. GET /jobs/{job_id} | payload hợp lệ | Queue jobs có thêm 1 message (Ready). GET trả status = "pending". Bảng jobs có 1 dòng tương ứng. | High |  |  |
| TC-API-06 | US-06, NFR-04 | Kiểm tra API còn sống | API đang chạy | 1. GET /health → Execute | (không có) | HTTP 200, body {"status":"ok"}. | Medium |  |  |
| TC-API-07 | FR-01, NFR-03 | RabbitMQ không khả dụng khi gửi yêu cầu | Dừng container RabbitMQ | 1. POST /jobs với payload hợp lệ<br>2. Bật lại RabbitMQ rồi GET /jobs/{job_id} (nếu có job_id) | payload hợp lệ | HTTP 503. Job (nếu đã lưu) có status = "failed", error_message = "Publish to queue failed". | Medium |  |  |

### 2.2 API tra cứu trạng thái (GET /jobs/{job_id})

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-GET-01 | FR-02, US-01 | Tra cứu job tồn tại | Đã tạo 1 job (TC-API-01) | 1. GET /jobs/{job_id}<br>2. Nhập job_id vừa nhận, bấm Execute | job_id hợp lệ | HTTP 200. Body đủ 7 trường: job_id, status, result, error_message, retry_count, created_at, updated_at. created_at và updated_at có dạng ...Z. | High |  |  |
| TC-GET-02 | FR-02 | Tra cứu job không tồn tại | API đang chạy | 1. GET /jobs/{job_id}<br>2. Nhập job_id không có trong DB | 00000000-0000-0000-0000-000000000000 | HTTP 404, body {"detail":"Job not found"}. | High |  |  |
| TC-GET-03 | FR-02 | Tra cứu với job_id sai định dạng | API đang chạy | 1. Mở trình duyệt, truy cập /jobs/not-a-uuid | not-a-uuid | HTTP 422 (job_id không phải UUID hợp lệ). | Medium |  |  |
| TC-GET-04 | FR-02 | Mất kết nối PostgreSQL khi tra cứu | Dừng container PostgreSQL | 1. GET /jobs/{job_id} với một job_id bất kỳ | job_id hợp lệ | HTTP 503, body {"detail":"Service unavailable"}. | Low |  |  |

### 2.3 Worker xử lý job

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-WRK-01 | FR-03, FR-08, US-01 | Xử lý thành công luồng đầu cuối | Cả hệ thống đang chạy; Mock Gemini trả 200 | 1. POST /jobs hợp lệ, ghi job_id<br>2. Đợi vài giây<br>3. GET /jobs/{job_id} | payload hợp lệ | status = "completed"; result là chuỗi có nội dung; error_message = null; retry_count = 0. | High |  |  |
| TC-WRK-02 | FR-08 | Ghi nhật ký các sự kiện của job | Đã chạy TC-WRK-01 | 1. Truy vấn bảng job_logs theo job_id | job_id của TC-WRK-01 | Có các event theo thứ tự: created, published, processing, completed. | Medium |  |  |
| TC-WRK-03 | FR-06 | Message sai định dạng bị chuyển vào DLQ | RabbitMQ UI mở sẵn | 1. RabbitMQ UI → Queues → jobs → Publish message<br>2. Gửi JSON thiếu job_id<br>3. Xem queue jobs.dlq | {"payload":"abc"} | Message nằm trong jobs.dlq (có header x-error). DB không bị cập nhật. | Medium |  |  |

### 2.4 Retry khi lỗi tạm thời

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-RTY-01 | FR-05, US-04 | Retry thành công sau lỗi 429 | Mock Gemini cấu hình trả 429 ở lần gọi đầu, 200 ở lần sau | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id} ngay sau đó<br>3. GET lại sau vài giây | payload hợp lệ | Lúc đầu status = "retrying", error_message ghi lỗi 429, retry_count tăng. Sau đó status = "completed". | High |  |  |
| TC-RTY-02 | FR-05, US-04 | Khoảng chờ retry tăng dần 1s, 2s, 4s | Mock Gemini luôn trả 500 | 1. POST /jobs hợp lệ<br>2. Quan sát log Mock và Worker, ghi thời điểm mỗi lần gọi | payload hợp lệ | Có tối đa 4 lần gọi Mock (1 lần đầu và 3 lần retry). Các lần retry cách nhau xấp xỉ 1s, 2s, 4s. | High |  |  |
| TC-RTY-03 | FR-05 | Retry khi Gemini quá thời gian chờ (timeout) | Mock Gemini cấu hình phản hồi chậm hơn thời gian timeout của Worker | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id} nhiều lần | payload hợp lệ | Worker coi timeout là lỗi tạm thời: status chuyển "retrying" và thử lại. | Medium |  |  |

### 2.5 Dead Letter Queue (DLQ) và lỗi vĩnh viễn

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-DLQ-01 | FR-06, US-02 | Hết 3 lần retry thì vào DLQ | Mock Gemini luôn trả 429 hoặc 500 | 1. POST /jobs hợp lệ<br>2. Đợi khoảng 10 giây<br>3. GET /jobs/{job_id}<br>4. Xem queue jobs.dlq trên RabbitMQ UI | payload hợp lệ | status = "failed"; retry_count = 3; error_message ghi lỗi gần nhất. Queue jobs.dlq có 1 message (header x-error, x-retry-count). job_logs có event moved_to_dlq. | High |  |  |
| TC-DLQ-02 | FR-05, US-02 | Lỗi vĩnh viễn không retry, không vào DLQ | Mock Gemini trả 400 | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id}<br>3. Xem queue jobs.dlq | payload hợp lệ | status = "failed" ngay, retry_count = 0, không có message mới ở jobs.dlq. job_logs có event failed. | High |  |  |
| TC-DLQ-03 | FR-07, US-02 | Admin đưa message từ DLQ về queue chính | Có ít nhất 1 message trong jobs.dlq; đã sửa nguyên nhân lỗi (Mock trả 200) | 1. RabbitMQ UI → Queues → jobs.dlq → Move messages<br>2. Chuyển sang queue jobs<br>3. GET /jobs/{job_id} | message trong DLQ | Worker xử lý lại message. (Ưu tiên thấp: giữa kỳ thực hiện thủ công, kết quả có thể là completed hoặc đã failed cần ghi nhận.) | Low |  |  |

### 2.6 Rate-limit và chịu tải

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-RL-01 | FR-04, US-03, NFR-05 | Số lần gọi Gemini không vượt 10 lần/giây | Một Worker; Mock Gemini ghi log thời điểm nhận | 1. Gửi 100 request POST /jobs liên tiếp (script hoặc Locust)<br>2. Đếm số request Mock nhận được mỗi giây | 100 payload hợp lệ | Mock nhận tối đa khoảng 10 request mỗi giây từ một Worker (RATE_LIMIT_PER_SECOND). | High |  |  |
| TC-RL-02 | FR-04, NFR-03 | Request vượt giới hạn phải chờ, không bị mất | Như TC-RL-01 | 1. Gửi 100 request<br>2. Đợi xử lý xong<br>3. Đếm số job theo status | 100 payload hợp lệ | Cả 100 job đều có kết quả cuối cùng (completed hoặc failed). Không job nào kẹt ở pending khi queue đã trống. | High |  |  |
| TC-NFR-01 | NFR-01, NFR-03, US-05 | Tăng tải 10 lần không mất message | Có kịch bản Locust (SCRUM-28) | 1. Chạy Locust ở mức tải 1x rồi 10x<br>2. Ghi throughput, error rate, latency<br>3. So sánh số job gửi và số job completed + failed | Kịch bản Locust | Số job completed + failed bằng số job đã gửi (không mất message). Có báo cáo throughput, error rate, latency cho cả hai mức tải. | High |  |  |

### 2.7 Hạ tầng triển khai

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-INF-01 | NFR-04, US-06 | Chạy toàn bộ hệ thống bằng một lệnh | Máy đã cài Docker; có file .env | 1. Chạy docker compose up --build<br>2. Chờ các dịch vụ khởi động<br>3. Mở /health và RabbitMQ UI | (không có) | RabbitMQ, PostgreSQL, API, Worker khởi động thành công. GET /health trả {"status":"ok"}. Gửi 1 request thử nhận được job_id. | High |  |  |

## 3. Ma trận truy vết yêu cầu – test case

Mỗi yêu cầu đều có ít nhất một test case kiểm tra.

| Yêu cầu | Nội dung | Test case kiểm tra |
|---|---|---|
| FR-01 | Gửi yêu cầu, trả job_id | TC-API-01, 02, 03, 04, 05 |
| FR-02 | Tra cứu trạng thái job | TC-GET-01, 02, 03, 04 |
| FR-03 | Đưa vào RabbitMQ; Worker xử lý và gọi Gemini | TC-WRK-01, TC-WRK-02 |
| FR-04 | Rate-limit, request chờ trong queue | TC-RL-01, TC-RL-02 |
| FR-05 | Retry 3 lần, backoff 1s/2s/4s | TC-RTY-01, 02, 03, TC-DLQ-02 |
| FR-06 | Chuyển message lỗi vào DLQ | TC-DLQ-01, TC-WRK-03 |
| FR-07 | Admin đưa message từ DLQ về queue chính | TC-DLQ-03 |
| FR-08 | Lưu trạng thái và kết quả vào PostgreSQL | TC-API-05, TC-WRK-01, TC-WRK-02 |
| NFR-01 | Chịu tải gấp 10 lần | TC-NFR-01 |
| NFR-02 | API trả job_id dưới 1 giây | TC-API-01 |
| NFR-03 | Không mất message | TC-RL-02, TC-NFR-01, TC-API-07 |
| NFR-04 | Chạy bằng một lệnh docker compose up | TC-INF-01, TC-API-06 |
| NFR-05 | Không vượt giới hạn gọi Gemini | TC-RL-01 |
