# SRS - Smart Warehouse AI Forecast (Giai đoạn 1: Prototype RabbitMQ)

## 1. Mục tiêu
Xây dựng pipeline xử lý request bất đồng bộ qua RabbitMQ khi gọi Gemini API ở quy mô lớn, có rate-limit, retry (exponential backoff) và Dead Letter Queue (DLQ).

## 2. Các tác nhân (Actor)
| Actor | Mô tả |
|---|---|
| Nhân viên kho | Gửi yêu cầu phân tích, xem trạng thái job |
| Admin hệ thống | Giám sát job, xử lý message lỗi trong DLQ |
| Gemini API | Dịch vụ AI bên ngoài (hoặc Mock Gemini khi test) |

## 3. Yêu cầu chức năng (FR)
| ID | Mô tả | Ưu tiên |
|---|---|---|
| FR-01 | Hệ thống cho phép người dùng gửi yêu cầu xử lý và trả về `job_id` ngay lập tức. | Cao |
| FR-02 | Hệ thống cho phép người dùng tra cứu trạng thái job theo `job_id` (pending / processing / done / failed). | Cao |
| FR-03 | Hệ thống đưa request vào RabbitMQ; Worker lấy message ra xử lý và gọi Gemini API. | Cao |
| FR-04 | Hệ thống giới hạn số request gọi Gemini mỗi giây (rate-limit); request vượt giới hạn phải chờ trong queue, không bị mất. | Cao |
| FR-05 | Khi gọi Gemini lỗi, hệ thống tự retry tối đa 3 lần với khoảng chờ tăng dần (exponential backoff). | Cao |
| FR-06 | Message vẫn lỗi sau 3 lần retry được chuyển vào DLQ kèm lý do lỗi. | Cao |
| FR-07 | Admin xem được danh sách message trong DLQ và đưa message về queue chính để xử lý lại. | Trung bình |
| FR-08 | Hệ thống lưu trạng thái và kết quả mỗi job vào PostgreSQL. | Cao |

## 4. Yêu cầu phi chức năng (NFR)
| ID | Mô tả |
|---|---|
| NFR-01 | Hệ thống chịu được lượng request tăng gấp 10 lần mà không mất dữ liệu. |
| NFR-02 | API trả `job_id` trong vòng dưới 1 giây (không chờ Gemini xử lý). |
| NFR-03 | Không có message nào bị mất: mỗi message hoặc xử lý thành công, hoặc nằm trong DLQ. |
| NFR-04 | Hệ thống chạy được bằng một lệnh `docker compose up`. |
| NFR-05 | Số lần gọi Gemini không vượt giới hạn cấu hình (ví dụ 10 lần/giây). |

## 5. Công nghệ
Go/FastAPI, RabbitMQ, PostgreSQL, Gemini API, Docker, Locust.
