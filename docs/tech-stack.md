# Tech Stack - Giai đoạn 1 (Prototype)

## 1. Công nghệ sử dụng
| Thành phần | Công nghệ | Mục đích |
|---|---|---|
| API | Python + FastAPI | Nhận request, trả `job_id`, tra cứu trạng thái job |
| Message Queue | RabbitMQ + thư viện `aio-pika` | Xử lý bất đồng bộ, rate-limit (prefetch), retry, DLQ |
| Database | PostgreSQL | Lưu trạng thái và kết quả job |
| AI | Gemini API (gói free) + Mock Gemini | Gọi AI; Mock dùng để giả lập chậm/lỗi 429 khi test |
| Triển khai | Docker + Docker Compose | Chạy toàn bộ hệ thống bằng `docker compose up` |
| Load test | Locust | Kiểm thử chịu tải 1x đến 10x |
| Quản lý | Jira + GitHub | Task, branch, Pull Request |

Tất cả đều miễn phí và chạy được trên máy cá nhân.

## 2. Luồng xử lý
Người dùng gửi request → **API** lưu job (status `pending`) và đẩy message vào **RabbitMQ** → trả `job_id` ngay → **Worker** lấy message theo giới hạn rate-limit → gọi **Gemini/Mock** → cập nhật kết quả vào **PostgreSQL**. Nếu lỗi thì retry (tăng dần khoảng chờ); quá 3 lần thì chuyển vào **DLQ**.

## 3. Cấu trúc thư mục
```
/api        - FastAPI (Chấn)
/worker     - Consumer, rate-limit, retry, DLQ (Bảo)
/gemini     - Gemini client + Mock server (Đại)
/loadtest   - Kịch bản Locust (Đoàn)
/docs       - Tài liệu (Dung)
docker-compose.yml  - (Đoàn)
```

## 4. Lưu ý
- Giới hạn của gói free Gemini cần được Đại kiểm tra lại trên tài liệu chính thức.
- Công nghệ do Tech Lead (Chấn) chốt cuối cùng.
