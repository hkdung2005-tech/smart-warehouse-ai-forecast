# Quy tắc làm việc với Git và Jira

## 1. Quy tắc đặt tên branch
Mẫu: `feature/SCRUM-<số ticket>-<mô tả ngắn>`

- `<số ticket>`: số của ticket trên Jira (ví dụ ticket SCRUM-15 thì ghi `SCRUM-15`).
- `<mô tả ngắn>`: tiếng Anh, không dấu, chữ thường, nối bằng dấu gạch ngang.
- Sửa lỗi thì dùng `bugfix/` thay cho `feature/`.

Ví dụ:
- `feature/SCRUM-15-worker-consumer`
- `feature/SCRUM-18-mock-gemini`
- `bugfix/SCRUM-30-retry-count-wrong`

## 2. Quy tắc commit message
Mẫu: `SCRUM-<số ticket>: <việc đã làm>`

Ví dụ:
- `SCRUM-15: Add worker consumer for job queue`
- `SCRUM-18: Add mock Gemini server returning 429`

Mỗi commit chỉ làm một việc nhỏ. Không viết "update", "fix" chung chung.

## 3. Quy trình làm việc
1. Nhận ticket trên Jira, chuyển sang **In Progress**.
2. Tạo branch từ `main` theo quy tắc ở mục 1.
3. Code trong **thư mục của mình** (xem `tech-stack.md`), commit theo mục 2.
4. Push branch lên GitHub, tạo **Pull Request** vào `main`.
5. Ghi mã ticket vào tiêu đề PR, ví dụ `SCRUM-15: Worker consumer`.
6. Có ít nhất 1 người khác xem lại (review), test chạy được rồi mới Merge.
7. Merge xong, chuyển ticket sang **Done**.

## 4. Nguyên tắc chung
- Không push code trực tiếp lên `main` (trừ tài liệu trong `docs/` và khung dự án ban đầu).
- Mỗi người chỉ sửa trong thư mục của mình để tránh xung đột. Cần sửa thư mục người khác thì nhắn họ.
- Gặp conflict thì nhắn nhóm, không tự xóa code của người khác.
- Không commit file bí mật (API key, mật khẩu). Dùng file `.env` và chỉ commit `.env.example`.
