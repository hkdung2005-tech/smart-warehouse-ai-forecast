# User Stories - Giai đoạn 1

Format: *As a [vai trò], I want [mục tiêu], so that [lợi ích]* + Acceptance Criteria (Given/When/Then)

Các giá trị cụ thể (số lần retry, thời gian chờ, giới hạn tốc độ) lấy theo cấu hình của Worker và `api-contract.md`.

---

## US-01: Gửi yêu cầu không phải chờ
Là một **nhân viên kho**, tôi muốn gửi yêu cầu phân tích mà không phải chờ AI trả lời ngay, để tôi tiếp tục làm việc khác.

**AC:**
- **Given** tôi gửi một yêu cầu hợp lệ, **When** hệ thống tiếp nhận, **Then** trả về `job_id` trong dưới 1 giây.
- **Given** tôi có `job_id`, **When** tôi tra cứu, **Then** thấy trạng thái pending / processing / retrying / completed / failed.

## US-02: Lưu message lỗi vào DLQ
Là một **Admin hệ thống**, tôi muốn các message xử lý thất bại được đưa vào DLQ, để tôi xem lại nguyên nhân gây lỗi.

**AC:**
- **Given** một message gọi Gemini API bị lỗi tạm thời (429, 5xx, timeout), **When** Worker đã retry đủ 3 lần, **Then** Worker chuyển message vào DLQ và job có trạng thái failed.
- **Given** message nằm trong DLQ, **When** Admin mở DLQ (qua RabbitMQ Management UI), **Then** thấy được nội dung message; lý do lỗi xem ở `error_message` của job.
- **Given** Admin đã xử lý nguyên nhân lỗi, **When** Admin đưa message từ DLQ về queue chính, **Then** message được xử lý lại. *(Ưu tiên thấp: thực hiện thủ công ở giữa kỳ, hoàn thiện ở cuối kỳ.)*

## US-03: Giới hạn số lần gọi Gemini (rate-limit)
Là một **Admin hệ thống**, tôi muốn hệ thống giới hạn số lần gọi Gemini API mỗi giây, để hạn chế lỗi 429 từ Gemini.

**AC:**
- **Given** có 1000 request gửi vào cùng lúc, **When** hệ thống xử lý, **Then** số lần gọi Gemini không vượt 10 lần/giây trên mỗi Worker (cấu hình `RATE_LIMIT_PER_SECOND`).
- **Given** request vượt giới hạn, **When** Worker chưa sẵn sàng nhận thêm, **Then** request chờ trong queue và không bị mất.

## US-04: Tự động thử lại khi lỗi tạm thời
Là một **nhân viên kho**, tôi muốn hệ thống tự thử lại khi Gemini lỗi tạm thời, để yêu cầu của tôi vẫn được xử lý mà tôi không phải gửi lại.

**AC:**
- **Given** Gemini trả lỗi 429, 5xx hoặc timeout, **When** Worker nhận lỗi, **Then** job chuyển sang trạng thái retrying và được thử lại sau 1 giây, 2 giây, 4 giây (tối đa 3 lần).
- **Given** lần retry thành công, **When** có kết quả, **Then** job chuyển sang trạng thái completed.

## US-05: Hệ thống chịu tải tăng 10 lần
Là một **Project Manager**, tôi muốn có số liệu kiểm thử khi request tăng 10 lần, để chứng minh hệ thống ổn định.

**AC:**
- **Given** kịch bản Locust chạy với tải 1x rồi 10x, **When** test kết thúc, **Then** có báo cáo throughput, error rate, latency.
- **Given** tải 10x, **When** hệ thống xử lý, **Then** không có message nào bị mất.

## US-06: Chạy hệ thống bằng một lệnh
Là một **thành viên nhóm**, tôi muốn chạy toàn bộ hệ thống bằng `docker compose up`, để dựng môi trường nhanh mà không cài thủ công.

**AC:**
- **Given** máy đã cài Docker, **When** chạy `docker compose up`, **Then** RabbitMQ, PostgreSQL và API khởi động thành công.
- **Given** hệ thống đã chạy, **When** gửi một request thử, **Then** nhận được `job_id`.
