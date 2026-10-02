# User Stories - Giai đoạn 1

Format: *As a [vai trò], I want [mục tiêu], so that [lợi ích]* + Acceptance Criteria (Given/When/Then)

---

## US-01: Gửi yêu cầu không phải chờ
Là một **nhân viên kho**, tôi muốn gửi yêu cầu phân tích mà không phải chờ AI trả lời ngay, để tôi tiếp tục làm việc khác.

**AC:**
- **Given** tôi gửi một yêu cầu hợp lệ, **When** hệ thống tiếp nhận, **Then** trả về `job_id` trong dưới 1 giây.
- **Given** tôi có `job_id`, **When** tôi tra cứu, **Then** thấy trạng thái pending / processing / done / failed.

## US-02: Lưu message lỗi vào DLQ
Là một **Admin hệ thống**, tôi muốn các message xử lý thất bại được đưa vào DLQ, để tôi xem lại nguyên nhân gây lỗi.

**AC:**
- **Given** một message gọi Gemini API bị lỗi, **When** đã retry đủ 3 lần, **Then** message được chuyển vào DLQ.
- **Given** message nằm trong DLQ, **When** Admin mở message đó, **Then** thấy được nội dung và lý do lỗi.
- **Given** Admin đã xử lý nguyên nhân lỗi, **When** Admin chọn "xử lý lại", **Then** message quay về queue chính để xử lý.

## US-03: Giới hạn số lần gọi Gemini (rate-limit)
Là một **Admin hệ thống**, tôi muốn hệ thống giới hạn số lần gọi Gemini API mỗi giây, để hạn chế lỗi 429 từ Gemini.

**AC:**
- **Given** có 1000 request gửi vào cùng lúc, **When** hệ thống xử lý, **Then** số lần gọi Gemini không vượt giới hạn cho phép (ví dụ 10 lần/giây).
- **Given** request vượt giới hạn, **When** Worker chưa sẵn sàng nhận thêm, **Then** request chờ trong queue và không bị mất.

## US-04: Tự động thử lại khi lỗi tạm thời
Là một **nhân viên kho**, tôi muốn hệ thống tự thử lại khi Gemini lỗi tạm thời, để yêu cầu của tôi vẫn được xử lý mà tôi không phải gửi lại.

**AC:**
- **Given** Gemini trả lỗi 429 hoặc timeout, **When** Worker nhận lỗi, **Then** retry sau khoảng chờ tăng dần (ví dụ 2s, 4s, 8s).
- **Given** lần retry thành công, **When** có kết quả, **Then** job chuyển sang trạng thái done.

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
