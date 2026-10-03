# Phân công vai trò nhóm

Dự án: Smart Warehouse – AI Forecast (Giai đoạn 1: Prototype RabbitMQ)

**mọi thành viên đều có nhiệm vụ kiểm thử** bên cạnh nhiệm vụ phát triển/tài liệu.

## 1. Thành viên, vai trò và nhiệm vụ kiểm thử
| Thành viên | Vai trò | Trách nhiệm chính | Nhiệm vụ kiểm thử | Thư mục phụ trách |
|---|---|---|---|---|
| Dung | Project Manager / Business Analyst | SRS, User Stories, Use Case, ERD, quản lý Jira, báo cáo | Viết test case, lập ma trận truy vết yêu cầu - test case, viết báo cáo kiểm thử | `docs/` |
| Chấn | Tech Lead / Backend | API (FastAPI), kiến trúc, API contract, triển khai (deploy) | Kiểm thử API: `POST /jobs`, `GET /jobs/{id}` (200/404/422/503); smoke test sau deploy | `api/` |
| Bảo | Backend | Worker consumer, queue RabbitMQ, rate-limit, retry, DLQ | Kiểm thử Worker: retry (1s/2s/4s), chuyển DLQ, rate-limit, lỗi vĩnh viễn không vào DLQ | `worker/` |
| Đại | Backend (AI) | Gemini client, Mock Gemini server | Kiểm thử Mock Gemini: trả đúng 200/429/500; kiểm thử Gemini client khi gặp lỗi và timeout | `gemini/` |
| Đoàn | DevOps / QA | docker-compose, Locust | Chạy test tích hợp, ghi bug vào Jira, kiểm thử tải Locust (1x và 10x), kiểm tra `docker compose up` | `docker-compose.yml`, `db/`, `loadtest/` |

## 2. Quy ước kiểm thử
- Mỗi người tự kiểm thử phần mình làm **trước khi** tạo Pull Request.
- Test case do Dung viết là cơ sở chung. Người phụ trách module chạy các test case của module mình và ghi kết quả (Pass/Fail).
- Lỗi phát hiện được ghi thành ticket loại Bug trên Jira, gán cho người phụ trách module.
- Đoàn tổng hợp kết quả chạy test tích hợp và tải; Dung tổng hợp vào báo cáo kiểm thử.

## 3. Quy ước phối hợp
- Mỗi người chỉ sửa trong thư mục của mình. Cần sửa thư mục người khác thì nhắn người đó.
- Mọi thay đổi code đi qua Pull Request vào `main`, có ít nhất 1 người review.
- Quy tắc branch và commit xem `git-rules.md`.
- Thay đổi API contract do Chấn quyết định, cả nhóm cùng được thông báo.

## 4. Bảng phân công có thể điều chỉnh cho dự án cuối kỳ 

