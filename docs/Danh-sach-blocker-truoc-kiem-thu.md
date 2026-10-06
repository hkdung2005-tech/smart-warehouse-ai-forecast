# Rà soát blocker trước kiểm thử

**Dự án:** Smart Warehouse AI Forecast  
**Phạm vi:** Phân loại theo các job SCRUM đang tiếp theo  
**Ngày rà soát:** 06/10/2026

> “Không tính blocker” nghĩa là không cần dừng để bắt đầu job đó; vấn đề vẫn phải được kiểm thử, ghi nhận hoặc xử lý trước khi tuyên bố yêu cầu tương ứng đã đạt.

## Tóm tắt

Có thể bắt đầu **SCRUM-27** (chạy test/ghi bug) và **SCRUM-28** (kịch bản Locust). Cần xác minh cấu hình RabbitMQ khi tích hợp/deploy. Hai lỗi/rủi ro đáng ghi nhận riêng là DLQ redrive không chạy lại job `failed` và khe hở giữa lưu DB với publish message. Chưa có căn cứ để xác nhận NFR-03 hoặc FR-07 đạt.

## Danh sách vấn đề

| Vấn đề | Job liên quan | Phân loại hiện tại | Lý do / hành động |
|---|---|---|---|
| Chưa có test tự động trong repo | SCRUM-27 – Chạy test, ghi bug Jira | Không chặn bắt đầu test | Có thể chạy test thủ công theo [test-cases.md](docs/test-cases.md). Phân biệt kết quả test thủ công với việc có regression automation. |
| Chưa có kịch bản Locust | SCRUM-28 – Kịch bản Locust | Không tính blocker cho tiến độ | Đây là phần việc của job SCRUM-28. Chưa thể kết luận NFR tải 10x đạt cho đến khi có kịch bản và số liệu. |
| RabbitMQ mặc định `guest/guest` | SCRUM-23 – Ghép code, tạo PR; SCRUM-29 – Deploy + smoke test | Cần xác minh khi tích hợp/deploy | RabbitMQ thường giới hạn `guest` chỉ kết nối nội bộ localhost. API/worker kết nối qua mạng Docker; nếu đang dùng mặc định này thì có thể bị từ chối. Xác minh `.env` an toàn, không chia sẻ secret. |
| Chuyển message DLQ về queue chính không xử lý lại job `failed` | SCRUM-27 – Chạy test/ghi bug; SCRUM-23 nếu sửa trong phạm vi tích hợp | Không chặn bắt đầu test; lỗi chức năng đã nhận diện | Worker ACK và bỏ qua job có trạng thái `failed`. Vì vậy thao tác redrive thủ công không đồng nghĩa job được xử lý lại. Ghi bug; retest trước khi đánh dấu FR-07 đạt. |
| Khe hở sau commit DB, trước publish RabbitMQ | SCRUM-27 – Kiểm thử/ghi bug; chưa thấy job sửa riêng | Rủi ro độ tin cậy chưa có phạm vi xử lý rõ | Nếu API dừng giữa hai bước, job có thể nằm `pending` trong DB nhưng không có message. Ghi risk/bug; luồng test bình thường không chứng minh NFR-03 trong tình huống crash. |
| `/health` trả `ok` tĩnh, không kiểm tra dependency | SCRUM-29 – Deploy + smoke test | Không tính blocker | Smoke test nên gửi `POST /jobs`, kiểm tra `GET /jobs/{id}`, xác nhận worker hoàn tất; không chỉ dựa vào `/health`. |

## Ưu tiên trước khi kết luận kiểm thử

1. Trong **SCRUM-29**, xác minh API và worker thực sự kết nối RabbitMQ với cấu hình hiện hành; tránh giữ `guest` mặc định nếu kết nối bị chặn.
2. Khi chạy **SCRUM-27**, chạy TC-DLQ-03 và ghi nhận hành vi redrive; không đánh dấu FR-07 đạt nếu worker vẫn bỏ qua trạng thái `failed`.
3. Ghi nhận khe hở DB–queue như bug/risk và làm rõ có cần xử lý trong phạm vi hiện tại hay không; không tuyên bố bảo đảm “không mất message” nếu chưa kiểm thử crash/recovery.
4. Trong **SCRUM-28**, thu số liệu tải 1x/10x và đối chiếu số job gửi với trạng thái cuối cùng; chưa có kết quả thì NFR-01 chưa được xác nhận.

## Kết quả kiểm tra trước đó

Docker Compose đã qua kiểm tra cấu hình (`docker compose config --quiet`). Đây chỉ là xác nhận cú pháp/resolve cấu hình; chưa khởi động container và chưa chạy test E2E hoặc load test.
