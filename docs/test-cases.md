# Tài liệu Test Case

Smart Warehouse – AI Forecast (Giai đoạn 1: Prototype RabbitMQ)

- **Mã ticket:** SCRUM-25
- **Người soạn:** Dung (PM/BA)
- **Ngày soạn:** 04/10/2026 – **Cập nhật:** 06/10/2026
- **Phiên bản:** 1.1
- **Căn cứ:** SRS (FR-01 đến FR-08, NFR-01 đến NFR-05), User Stories (US-01 đến US-06), API Contract v1.3, `worker/README.md`, `gemini/README.md`, `Danh-sach-blocker-truoc-kiem-thu.md` (Chấn, 06/10/2026)

## 0. Lịch sử thay đổi

| Phiên bản | Ngày | Nội dung |
|---|---|---|
| 1.0 | 04/10/2026 | Bản nháp đầu tiên, 24 test case |
| 1.1 | 06/10/2026 | Siết chặt kết quả mong đợi; dữ liệu test theo tag của Mock Gemini; thêm TC-WRK-04 và TC-INF-02; viết lại TC-DLQ-03; thêm mục lỗi đã biết (mục 3) và rủi ro chưa kiểm thử được (mục 4); cập nhật ma trận truy vết. Tổng 26 test case |

## 1. Phạm vi, môi trường và quy ước

- Tài liệu gồm 26 test case, chia theo nhóm chức năng. Mỗi test case ghi rõ yêu cầu (FR/NFR/US) mà nó kiểm tra.
- Cột "Kết quả thực tế" và "Trạng thái" để trống, người phụ trách module điền khi chạy test. Trạng thái chỉ dùng 3 giá trị: **Pass**, **Fail**, **Blocked** (không chạy được vì phụ thuộc chưa xong, ghi rõ lý do).
- Test case **Fail**: tạo ticket Bug trên Jira, gán cho người phụ trách module và ghi mã Bug (SCRUM-xx) vào cột "Kết quả thực tế". Lỗi trùng với mục 3 thì ghi thêm mã KI tương ứng.
- Mức ưu tiên: High = chức năng cốt lõi; Medium = quan trọng; Low = mở rộng hoặc thực hiện thủ công.

**Môi trường chạy test**

- Khởi động: `docker compose up --build` (cần file `.env` sao chép từ `.env.example`).
- API Swagger: `http://localhost:8000/docs`. RabbitMQ UI: `http://localhost:15672`. Mock Gemini: `http://localhost:9000`.
- Truy vấn DB: `docker compose exec postgres psql -U postgres -d warehouse -c "<câu SQL>"`.
- Dừng/bật dịch vụ: `docker compose stop <tên>` và `docker compose start <tên>` (rabbitmq, postgres, worker).

**Quy ước dữ liệu test với Mock Gemini** (theo `gemini/README.md`)

- Tag `[mock:<mode>]` phải nằm **ở đầu payload**, không có khoảng trắng hay ký tự nào phía trước. Tag có ưu tiên cao hơn mode toàn cục.
- Mỗi lần chạy, thêm `id=<mã duy nhất>` vào payload (ví dụ `id=a1b2c3d4`), vì mode `fail_n` đếm lỗi theo nội dung payload.
- Gọi `POST http://localhost:9000/admin/reset` **trước mỗi test dùng Mock**. Xem số lần gọi bằng `GET http://localhost:9000/admin/stats`.
- Không dùng `[mock:timeout]` ngoài TC-RTY-03 và không dùng khi chạy test tải.
- Chạy lần lượt từng test case có dùng Mock, không chạy song song: mỗi Worker chỉ xử lý một job tại một thời điểm.

## 2. Danh sách test case

### 2.1 API tạo job (POST /jobs) và kiểm tra hệ thống

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-API-01 | FR-01, US-01, NFR-02 | Gửi yêu cầu hợp lệ | Hệ thống đang chạy (TC-INF-01 đã Pass) | 1. Mở `/docs`<br>2. POST /jobs → Try it out<br>3. Nhập body, bấm Execute<br>4. Đo thời gian phản hồi (DevTools Network hoặc `curl -w "%{time_total}"`)<br>5. Truy vấn `job_logs` theo `job_id` | `{"payload":"Dự báo lượng hàng tồn kho cần nhập cho sản phẩm A"}` | HTTP 202. Body có đúng 3 trường: `job_id` (UUID), `status` = "pending", `created_at` dạng ...Z. Thời gian phản hồi dưới 1 giây. Bảng `jobs` có 1 dòng mới; `job_logs` có event `created` và `published`. | High |  |  |
| TC-API-02 | FR-01 | Gửi payload rỗng hoặc toàn khoảng trắng | API đang chạy; ghi lại số dòng bảng `jobs` | 1. POST /jobs với payload rỗng<br>2. POST /jobs với payload chỉ có khoảng trắng<br>3. Đếm lại số dòng bảng `jobs` | `{"payload":""}` và `{"payload":"   "}` | Cả hai lần HTTP 422, `detail` cho biết payload không được rỗng. Số dòng bảng `jobs` không đổi. | High |  |  |
| TC-API-03 | FR-01 | Gửi thiếu trường payload | API đang chạy; ghi lại số dòng bảng `jobs` | 1. POST /jobs<br>2. Nhập body, bấm Execute<br>3. Đếm lại số dòng bảng `jobs` | `{}` | HTTP 422, `detail` chỉ ra thiếu trường bắt buộc `payload`. Số dòng bảng `jobs` không đổi. | High |  |  |
| TC-API-04 | FR-01 | Gửi payload sai kiểu dữ liệu | API đang chạy; ghi lại số dòng bảng `jobs` | 1. POST /jobs<br>2. Nhập body, bấm Execute<br>3. Đếm lại số dòng bảng `jobs` | `{"payload":123}` | HTTP 422, `detail` cho biết payload phải là chuỗi. Số dòng bảng `jobs` không đổi. | Medium |  |  |
| TC-API-05 | FR-01, FR-08 | Job được lưu DB và đưa vào queue | Chạy `docker compose stop worker` để message không bị lấy đi | 1. POST /jobs hợp lệ, ghi lại `job_id`<br>2. RabbitMQ UI → Queues → `jobs`, xem cột Ready<br>3. GET /jobs/{job_id}<br>4. Chạy `docker compose start worker` để dọn dẹp | payload hợp lệ | Queue `jobs` có đúng 1 message ở trạng thái Ready. GET trả `status` = "pending", `retry_count` = 0, `result` = null. Bảng `jobs` có 1 dòng với `job_id` tương ứng. | High |  |  |
| TC-API-06 | US-06, NFR-04 | Kiểm tra API còn sống | API đang chạy | 1. GET /health → Execute | (không có) | HTTP 200, body `{"status":"ok"}`. Ghi chú: `/health` chỉ cho biết API sống, không kiểm tra RabbitMQ hay PostgreSQL (xem KI-05). | Medium |  |  |
| TC-API-07 | FR-01, NFR-03 | RabbitMQ không khả dụng khi gửi yêu cầu | Chạy `docker compose stop rabbitmq` | 1. POST /jobs với payload hợp lệ, ghi mã HTTP<br>2. Chạy `docker compose start rabbitmq`<br>3. Truy vấn job mới nhất: `SELECT job_id, status, error_message FROM jobs ORDER BY created_at DESC LIMIT 1;`<br>4. Truy vấn `job_logs` của job đó | payload hợp lệ | HTTP 503, body `{"detail":"Service unavailable"}` (không có `job_id` trong response nên phải tra DB). Job mới nhất có `status` = "failed", `error_message` = "Publish to queue failed". `job_logs` có event `created` và `publish_failed`, không có `published`. | Medium |  |  |

### 2.2 API tra cứu trạng thái (GET /jobs/{job_id})

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-GET-01 | FR-02, US-01 | Tra cứu job tồn tại | Đã tạo 1 job (TC-API-01) | 1. GET /jobs/{job_id}<br>2. Nhập `job_id` vừa nhận, bấm Execute | `job_id` hợp lệ | HTTP 200. Body đủ 7 trường: `job_id`, `status`, `result`, `error_message`, `retry_count`, `created_at`, `updated_at`. `status` là một trong 5 giá trị hợp lệ (pending, processing, retrying, completed, failed). `created_at` và `updated_at` có dạng ...Z. | High |  |  |
| TC-GET-02 | FR-02 | Tra cứu job không tồn tại | API đang chạy | 1. GET /jobs/{job_id}<br>2. Nhập `job_id` không có trong DB | `00000000-0000-0000-0000-000000000000` | HTTP 404, body `{"detail":"Job not found"}`. | High |  |  |
| TC-GET-03 | FR-02 | Tra cứu với job_id sai định dạng | API đang chạy | 1. Mở trình duyệt, truy cập `http://localhost:8000/jobs/not-a-uuid` | `not-a-uuid` | HTTP 422, `detail` cho biết `job_id` không phải UUID hợp lệ. | Medium |  |  |
| TC-GET-04 | FR-02 | Mất kết nối PostgreSQL khi tra cứu | Chạy `docker compose stop postgres` | 1. GET /jobs/{job_id} với một `job_id` bất kỳ<br>2. Chạy `docker compose start postgres`, đợi 10 giây<br>3. GET lại cùng `job_id` | `job_id` hợp lệ | Bước 1: HTTP 503, body `{"detail":"Service unavailable"}`. Bước 3: API phục hồi, trả 200 hoặc 404 (không còn 503). | Low |  |  |

### 2.3 Worker xử lý job

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-WRK-01 | FR-03, FR-08, US-01 | Xử lý thành công luồng đầu cuối | Cả hệ thống đang chạy; Mock ở chế độ mặc định (success); đã `POST /admin/reset` | 1. POST /jobs hợp lệ, ghi `job_id`<br>2. Đợi 5 giây<br>3. GET /jobs/{job_id}<br>4. `GET /admin/stats` trên Mock | payload hợp lệ (không có tag) | Trong vòng 5 giây: `status` = "completed"; `result` là chuỗi có nội dung (bắt đầu bằng "Forecast result for:"); `error_message` = null; `retry_count` = 0. Mock `total_requests` = 1. | High |  |  |
| TC-WRK-02 | FR-08 | Ghi nhật ký các sự kiện của job | Đã chạy TC-WRK-01 | 1. Truy vấn: `SELECT event, created_at FROM job_logs WHERE job_id = '<job_id>' ORDER BY log_id;` | `job_id` của TC-WRK-01 | Có đủ 4 event: `created`, `published`, `processing`, `completed`. `created` đứng đầu, `completed` đứng cuối. `published` và `processing` có thể đổi chỗ cho nhau vì API ghi `published` sau khi publish xong, lúc đó Worker có thể đã nhận message. Không có event `failed`. | Medium |  |  |
| TC-WRK-03 | FR-06 | Message sai định dạng bị chuyển vào DLQ | RabbitMQ UI mở sẵn; ghi lại số dòng bảng `jobs` và `job_logs` | 1. RabbitMQ UI → Queues → `jobs` → Publish message<br>2. Gửi JSON thiếu `job_id`<br>3. Lặp lại với nội dung không phải JSON<br>4. Xem queue `jobs.dlq`<br>5. Đếm lại số dòng bảng `jobs` và `job_logs` | Lần 1: `{"payload":"abc"}`<br>Lần 2: `abc` | Cả 2 message nằm trong `jobs.dlq`, có header `x-error` mô tả lý do. Queue `jobs` không còn message Ready hay Unacked. Bảng `jobs` và `job_logs` không có dòng mới. | Medium |  |  |
| TC-WRK-04 | FR-03, FR-08 | Message trùng của job đã xong bị bỏ qua | Job ở TC-WRK-01 đang `completed`; ghi lại `result`, `updated_at` và số dòng `job_logs` của job đó; đã `POST /admin/reset` | 1. RabbitMQ UI → Queues → `jobs` → Publish message với `job_id` của TC-WRK-01<br>2. Đợi 5 giây<br>3. GET /jobs/{job_id}<br>4. Đếm lại `job_logs` và xem Mock `/admin/stats` | `{"job_id":"<job_id TC-WRK-01>","payload":"abc","retry_count":0}` | Message được ack: queue `jobs` Ready = 0, Unacked = 0. `status` vẫn "completed", `result` và `updated_at` không đổi. `job_logs` không có event mới. Mock `total_requests` = 0 (không gọi lại Gemini). | Medium |  |  |

### 2.4 Retry khi lỗi tạm thời

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-RTY-01 | FR-05, US-04 | Retry thành công sau lỗi 429 | Đã `POST /admin/reset` | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id} ngay sau đó (trong 1–3 giây)<br>3. GET lại sau khoảng 10 giây<br>4. Xem Mock `/admin/stats` và `job_logs` | `[mock:fail_n:2] id=<mã duy nhất> Du bao ton kho SKU-001` (Mock trả 429 hai lần đầu, lần thứ ba trả 200) | Bước 2 (có thể thấy): `status` = "retrying", `error_message` = "Gemini returned HTTP 429", `retry_count` tăng. Bước 3: `status` = "completed", `result` có nội dung, `error_message` = null, `retry_count` = 2. Mock nhận đúng 3 lần gọi cho payload này. `job_logs`: `retry_scheduled` 2 lần, `processing` 3 lần, `completed` 1 lần. | High |  |  |
| TC-RTY-02 | FR-05, US-04 | Khoảng chờ retry tăng dần 1s, 2s, 4s | Đã `POST /admin/reset` | 1. POST /jobs hợp lệ<br>2. Chạy `docker compose logs gemini` sau khoảng 10 giây, ghi thời điểm 4 lần gọi<br>3. `GET /admin/stats` | `[mock:500] id=<mã duy nhất> Du bao ton kho SKU-002` | Mock nhận đúng 4 lần gọi cho payload này (1 lần đầu và 3 lần retry; `max_calls_per_payload` = 4). Các lần gọi cách nhau xấp xỉ 1s, 2s, 4s (sai số ±1 giây vì log Mock ghi theo giây). Không có lần gọi thứ 5. | High |  |  |
| TC-RTY-03 | FR-05 | Retry khi Gemini quá thời gian chờ (timeout) | Đã `POST /admin/reset`; không chạy TC nào khác cùng lúc (mỗi lần gọi chiếm Worker 60 giây, tổng hơn 4 phút) | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id} sau khoảng 70 giây<br>3. GET lại sau khoảng 4 phút 10 giây kể từ lúc gửi<br>4. Xem queue `jobs.dlq` | `[mock:timeout] id=<mã duy nhất> Du bao ton kho SKU-003` | Worker coi timeout là lỗi tạm thời. Bước 2: `status` = "retrying", `retry_count` = 1, `error_message` mô tả lỗi timeout. Bước 3: `status` = "failed", `retry_count` = 3, `job_logs` có `moved_to_dlq`, `jobs.dlq` có 1 message. Mock nhận đúng 4 lần gọi. | Medium |  |  |

### 2.5 Dead Letter Queue (DLQ) và lỗi vĩnh viễn

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-DLQ-01 | FR-06, US-02 | Hết 3 lần retry thì vào DLQ | Đã `POST /admin/reset`; ghi lại số message trong `jobs.dlq` | 1. POST /jobs hợp lệ<br>2. Đợi khoảng 10 giây<br>3. GET /jobs/{job_id}<br>4. Xem queue `jobs.dlq` trên RabbitMQ UI<br>5. Truy vấn `job_logs` và Mock `/admin/stats` | `[mock:429] id=<mã duy nhất> Du bao ton kho SKU-004` | `status` = "failed"; `retry_count` = 3; `error_message` = "Gemini returned HTTP 429". `jobs.dlq` tăng đúng 1 message (header `x-error`, `x-retry-count` = 3). `job_logs`: `retry_scheduled` 3 lần và `moved_to_dlq` 1 lần, không có event `failed`. Mock nhận đúng 4 lần gọi. | High |  |  |
| TC-DLQ-02 | FR-05, US-02 | Lỗi vĩnh viễn không retry, không vào DLQ | Đã `POST /admin/reset`; ghi lại số message trong `jobs.dlq` | 1. POST /jobs hợp lệ<br>2. GET /jobs/{job_id} sau 3 giây<br>3. Xem queue `jobs.dlq`<br>4. Truy vấn `job_logs` và Mock `/admin/stats`<br>5. Lặp lại với 2 payload còn lại | Lần 1: `[mock:400] id=<mã duy nhất> ...`<br>Lần 2: `[mock:bad_json] id=<mã duy nhất> ...`<br>Lần 3: `[mock:not_json] id=<mã duy nhất> ...` | Với cả 3 payload: `status` = "failed" ngay, `retry_count` = 0, `error_message` có nội dung (lần 1 là "Gemini returned HTTP 400"). Số message `jobs.dlq` không đổi. `job_logs` có event `failed`, không có `retry_scheduled` hay `moved_to_dlq`. Mock nhận đúng 1 lần gọi cho mỗi payload. | High |  |  |
| TC-DLQ-03 | FR-07, US-02 | Admin đưa message từ DLQ về queue chính | Hệ thống đang chạy. Lưu ý: không dùng payload có tag `[mock:...]` vì tag luôn thắng mode toàn cục, message đưa lại vẫn bị lỗi | 1. `POST /admin/mode` với `{"mode":"500"}`<br>2. POST /jobs với payload thường, đợi 10 giây, xác nhận job `failed` và có 1 message trong `jobs.dlq`<br>3. `POST /admin/mode` với `{"mode":"default"}`<br>4. RabbitMQ UI → Queues → `jobs.dlq` → Move messages, chọn đích là `jobs`<br>5. Đợi 5 giây, GET /jobs/{job_id} | payload thường, không có tag, ví dụ `Du bao ton kho SKU-005 id=<mã duy nhất>` | Worker xử lý lại message: `status` chuyển từ "failed" sang "processing" rồi "completed", `result` có nội dung, `jobs.dlq` còn 0 message. Nếu `status` vẫn "failed" và Worker bỏ qua message thì **Fail**: đây là lỗi đã biết KI-02, tạo Bug và không kết luận FR-07 đạt. | Medium |  |  |

### 2.6 Rate-limit và chịu tải

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-RL-01 | FR-04, US-03, NFR-05 | Số lần gọi Gemini không vượt 10 lần/giây | Chỉ có 1 Worker (`docker compose ps`); Mock ở chế độ success; đã `POST /admin/reset` | 1. Gửi 100 request POST /jobs liên tiếp (script hoặc Locust)<br>2. Đợi đến khi queue `jobs` về 0<br>3. Chạy `docker compose logs gemini`, đếm số request Mock nhận theo từng giây | 100 payload hợp lệ, mỗi payload có `id=<mã duy nhất>`, không có tag | Không giây nào vượt 10 request (cho phép lệch ±1 do độ trễ mạng và timestamp làm tròn giây, ghi lại số đo thực tế). Tổng thời gian xử lý 100 job khoảng 10 giây trở lên. Mock `total_requests` = 100. | High |  |  |
| TC-RL-02 | FR-04, NFR-03 | Request vượt giới hạn phải chờ, không bị mất | Như TC-RL-01 | 1. Gửi 100 request<br>2. Trong lúc xử lý, GET vài job: thấy "pending" hoặc "processing"<br>3. Đợi queue `jobs` về 0<br>4. Truy vấn: `SELECT status, COUNT(*) FROM jobs GROUP BY status;` | 100 payload hợp lệ, mỗi payload có `id=<mã duy nhất>` | Bước 2 có job còn chờ (không bị từ chối). Bước 4: tổng 100 job, `completed` = 100 (Mock success), `pending`, `processing`, `retrying` đều bằng 0. Queue `jobs` Ready = 0 và Unacked = 0. | High |  |  |
| TC-NFR-01 | NFR-01, NFR-03, US-05 | Tăng tải 10 lần không mất message | Có kịch bản Locust (SCRUM-28), nếu chưa có thì ghi Blocked; đã `POST /admin/reset` trước mỗi mức tải | 1. Chạy Locust ở mức tải 1x, ghi số request POST trả 202<br>2. Đợi queue `jobs` về 0, đối chiếu với số job `completed` + `failed`<br>3. Reset Mock, chạy mức tải 10x, đối chiếu tương tự<br>4. Ghi throughput, error rate, latency cho cả hai mức | Kịch bản Locust; mỗi request có `id=<mã duy nhất>`; không dùng tag `[mock:timeout]` | Với mỗi mức tải: số job gửi thành công (202) bằng số job `completed` + `failed`; không job nào còn `pending`, `processing` hay `retrying` sau khi queue trống. Có báo cáo throughput, error rate, latency cho cả 1x và 10x. Lưu ý: 1 Worker xử lý tối đa 10 lần/giây nên mức 10x cần thời gian chờ lâu hơn. | High |  |  |

### 2.7 Hạ tầng triển khai

| TC ID | Yêu cầu | Tên test case | Điều kiện trước | Các bước | Dữ liệu test | Kết quả mong đợi | Ưu tiên | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|---|---|---|---|
| TC-INF-01 | NFR-04, US-06 | Chạy toàn bộ hệ thống bằng một lệnh | Máy đã cài Docker; có file `.env` | 1. Chạy `docker compose up --build`<br>2. Chờ các dịch vụ khởi động<br>3. Chạy `docker compose ps`<br>4. Mở `/health` và RabbitMQ UI<br>5. Truy vấn: `SELECT COUNT(*) FROM jobs;` và `SELECT COUNT(*) FROM job_logs;`<br>6. POST /jobs thử, chờ vài giây, GET /jobs/{job_id} | payload hợp lệ | 5 dịch vụ (rabbitmq, postgres, api, worker, gemini) ở trạng thái Up; rabbitmq, postgres, gemini là healthy. GET /health trả `{"status":"ok"}`. Hai bảng `jobs` và `job_logs` tồn tại (câu SQL chạy không lỗi). POST /jobs nhận được `job_id` và job chuyển "completed". | High |  |  |
| TC-INF-02 | FR-03, NFR-04 | API và Worker kết nối được RabbitMQ | Hệ thống chạy từ TC-INF-01 với tài khoản RabbitMQ trong `.env` | 1. Chạy `docker compose logs api`<br>2. Chạy `docker compose logs worker`<br>3. RabbitMQ UI → Connections<br>4. RabbitMQ UI → Queues | (không có) | Log API có dòng "RabbitMQ connection ready" và "Queues declared". Log Worker có dòng "Consuming jobs". Không có lỗi `ACCESS_REFUSED`, `PRECONDITION_FAILED`, và không lặp lại dòng "reconnecting in 3 seconds". Tab Connections có kết nối của API và Worker. Tab Queues có đủ 5 queue durable: `jobs`, `jobs.dlq`, `jobs.retry.1s`, `jobs.retry.2s`, `jobs.retry.4s`. Nếu Fail, xem KI-03. | High |  |  |

## 3. Lỗi đã biết trước khi kiểm thử

Nguồn: `Danh-sach-blocker-truoc-kiem-thu.md` (Chấn, 06/10/2026). Danh sách này không chặn việc bắt đầu SCRUM-27 nhưng ảnh hưởng đến cách kết luận kết quả.

| Mã | Vấn đề | Test case liên quan | Cách xử lý khi chạy test |
|---|---|---|---|
| KI-01 | Chưa có test tự động trong repo | Toàn bộ | Chạy thủ công theo tài liệu này. Kết quả thủ công không thay thế regression automation. |
| KI-02 | Chuyển message từ DLQ về queue chính không xử lý lại job `failed` (Worker ack và bỏ qua job đã `failed`) | TC-DLQ-03 | Dự kiến **Fail**. Tạo Bug, retest sau khi sửa. Chưa kết luận FR-07 đạt. |
| KI-03 | RabbitMQ dùng `guest/guest` mặc định, có thể bị từ chối khi kết nối qua mạng Docker (cần xác minh) | TC-INF-01, TC-INF-02 | Nếu Fail, tạo Bug cho Chấn. Không chia sẻ secret trong báo cáo hay trên GitHub. |
| KI-04 | Khe hở giữa commit DB và publish RabbitMQ | Không có (xem mục 4) | Ghi nhận như rủi ro, không tuyên bố bảo đảm "không mất message" khi API sập. |
| KI-05 | `/health` trả `ok` tĩnh, không kiểm tra phụ thuộc | TC-API-06 | Dùng TC-WRK-01 và TC-INF-01 (POST rồi GET job) làm smoke test, không chỉ dựa vào `/health`. |
| KI-06 | Chưa có kịch bản Locust (SCRUM-28) | TC-RL-01, TC-RL-02, TC-NFR-01 | Ghi Blocked nếu chưa có kịch bản. Chưa xác nhận NFR-01 cho đến khi có số liệu 1x và 10x. |

## 4. Rủi ro chưa kiểm thử được

| Mã | Mô tả rủi ro | Yêu cầu liên quan | Lý do chưa kiểm thử | Đề xuất |
|---|---|---|---|---|
| R-01 | API commit job vào DB xong rồi mới publish vào RabbitMQ. Nếu API dừng giữa hai bước, job nằm "pending" trong DB nhưng không có message trong queue (đồng nghĩa KI-04). | NFR-03 | Cần dừng API đúng khoảnh khắc giữa hai bước, không thể tái hiện ổn định bằng thao tác thủ công. TC-API-07 chỉ kiểm tra RabbitMQ lỗi lúc publish, không phủ trường hợp này. | Ghi Risk/Bug trên Jira. Chấn quyết định có xử lý trong phạm vi giữa kỳ hay để sang cuối kỳ. Trong báo cáo ghi NFR-03 là "kiểm thử một phần". |

## 5. Ma trận truy vết yêu cầu – test case

Mỗi yêu cầu đều có ít nhất một test case kiểm tra.

| Yêu cầu | Nội dung | Test case kiểm tra | Ghi chú |
|---|---|---|---|
| FR-01 | Gửi yêu cầu, trả job_id | TC-API-01, 02, 03, 04, 05, 07 | |
| FR-02 | Tra cứu trạng thái job | TC-GET-01, 02, 03, 04 | |
| FR-03 | Đưa vào RabbitMQ; Worker xử lý và gọi Gemini | TC-WRK-01, 02, 04, TC-INF-02 | |
| FR-04 | Rate-limit, request chờ trong queue | TC-RL-01, 02 | Cần SCRUM-28 nếu dùng Locust (KI-06) |
| FR-05 | Retry 3 lần, backoff 1s/2s/4s | TC-RTY-01, 02, 03, TC-DLQ-02 | |
| FR-06 | Chuyển message lỗi vào DLQ | TC-DLQ-01, TC-WRK-03 | |
| FR-07 | Admin đưa message từ DLQ về queue chính | TC-DLQ-03 | Dự kiến Fail (KI-02) |
| FR-08 | Lưu trạng thái và kết quả vào PostgreSQL | TC-API-05, TC-WRK-01, 02 | |
| NFR-01 | Chịu tải gấp 10 lần | TC-NFR-01 | Cần SCRUM-28 (KI-06) |
| NFR-02 | API trả job_id dưới 1 giây | TC-API-01 | |
| NFR-03 | Không mất message | TC-RL-02, TC-NFR-01, TC-API-07 | Kiểm thử một phần; rủi ro R-01 chưa kiểm thử |
| NFR-04 | Chạy bằng một lệnh docker compose up | TC-INF-01, 02, TC-API-06 | |
| NFR-05 | Không vượt giới hạn gọi Gemini | TC-RL-01 | |
