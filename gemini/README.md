# Mock Gemini Server

Mock server giả lập Google Gemini API cho hệ thống **Smart Warehouse AI Forecast**, được xây dựng bằng **Python + FastAPI + Uvicorn**.

Server này hỗ trợ giả lập đầy đủ các tình huống nghiệp vụ: phản hồi thành công, độ trễ tùy chỉnh, lỗi tạm thời (429, 500, timeout), lỗi vĩnh viễn (400, bad JSON, non-JSON), flaky ngẫu nhiên, và cơ chế `fail_n` hỗ trợ kiểm thử luồng retry / Dead Letter Queue (DLQ).

> **Yêu cầu môi trường**: Python >= 3.10 (do sử dụng `asyncio.Lock` ở module-level).

---

## 1. Hướng dẫn khởi chạy

### Chạy Local (Trực tiếp bằng Python)

1. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r gemini/requirements.txt
   ```

2. Khởi chạy server:
   ```bash
   cd gemini
   uvicorn mock_server:app --host 0.0.0.0 --port 9000
   # hoặc:
   # python mock_server.py
   ```

### Chạy bằng Docker

1. Build Docker image:
   ```bash
   docker build -t warehouse-gemini-mock ./gemini
   ```

2. Khởi chạy container:
   ```bash
   docker run -d -p 9000:9000 --name gemini_mock warehouse-gemini-mock
   ```

### Chạy trong Docker Compose

Đoạn cấu hình mẫu để tích hợp vào `docker-compose.yml` (dành cho người phụ trách Compose):

```yaml
services:
  gemini:
    build: ./gemini
    ports:
      - "9000:9000"

  worker:
    environment:
      GEMINI_API_URL: http://gemini:9000/generate
    depends_on:
      gemini:
        condition: service_healthy
```

> **Lưu ý quan trọng**: Trong Docker Compose, worker phải kết nối qua tên service `http://gemini:9000/generate`, tuyệt đối **không dùng `localhost`** vì `localhost` bên trong container worker là chính nó.

---

## 2. Dùng trên Windows PowerShell

Khi kiểm thử bằng PowerShell trên Windows:
- Lệnh `curl` mặc định là alias của `Invoke-WebRequest`, do đó bạn phải gọi chính xác **`curl.exe`**.
- PowerShell tự động xử lý và làm mất các dấu nháy kép (`"`) trong chuỗi JSON truyền qua `-d`, khiến server FastAPI nhận chuỗi JSON lỗi và trả về mã lỗi `422 (JSON decode error)`.

### Cách 1 (Khuyến nghị): Ghi JSON ra file tạm rồi gửi bằng `--data-binary`
```powershell
'{"payload":"[mock:429] test"}' | Out-File -Encoding ascii body.json
curl.exe -i -X POST http://localhost:9000/generate -H "Content-Type: application/json" --data-binary "@body.json"
```
*(Nhớ xóa file `body.json` sau khi test xong, không `git add` file này).*

### Cách 2: Sử dụng `Invoke-RestMethod`
```powershell
# Gửi request thành công
$body = @{ payload = "[mock:success] test" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:9000/generate -Method POST -ContentType "application/json" -Body $body

# Bắt lỗi HTTP status (4xx / 5xx):
try {
    $errBody = @{ payload = "[mock:429] test rate limit" } | ConvertTo-Json
    Invoke-RestMethod -Uri http://localhost:9000/generate -Method POST -ContentType "application/json" -Body $errBody
} catch {
    Write-Host "HTTP Status:" $_.Exception.Response.StatusCode.value__
}
```

---

## 3. Biến môi trường cấu hình

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `PORT` | `9000` | Cổng HTTP lắng nghe của server |
| `MOCK_MODE` | `success` | Mode mặc định khi server khởi động |
| `MOCK_DELAY` | `2.0` | Số giây `asyncio.sleep` khi chạy mode `slow` (nếu tag không chỉ định) |
| `MOCK_ERROR_RATE` | `0.3` | Xác suất trả lỗi (429 hoặc 500) khi chạy mode `flaky` (0.0 đến 1.0) |
| `MOCK_FAIL_COUNT` | `2` | Số lần trả lỗi 429 cho mỗi payload trước khi thành công trong mode `fail_n` |

---

## 4. Danh sách các Mode giả lập

| Mode | Trả về (Status Code & Body) | Ý nghĩa / Hành vi Worker |
|---|---|---|
| `success` | `200 OK` + `{"result": "..."}` | Thành công bình thường, worker lưu kết quả vào DB. |
| `slow` | Chờ `delay` giây rồi trả `200 OK` | Giả lập phản hồi chậm. Có thể truyền số giây qua tag: `[mock:slow:5]`. |
| `429` | `429 Too Many Requests` (Body rỗng) | Lỗi Rate Limit tạm thời -> Worker retry (1s/2s/4s) rồi chuyển vào DLQ. |
| `500` | `500 Internal Server Error` (Body rỗng) | Lỗi Server tạm thời -> Worker retry rồi chuyển vào DLQ. |
| `400` | `400 Bad Request` (Body rỗng) | Lỗi vĩnh viễn (Client error) -> Worker đánh dấu FAILED ngay, không retry, không vào DLQ. |
| `timeout` | Chờ `90` giây rồi trả `200 OK` | Vượt timeout 60s của Worker -> Worker timeout -> Coi là lỗi tạm thời, retry rồi vào DLQ. |
| `bad_json` | `200 OK` + JSON thiếu key `result` | Phản hồi sai schema -> Worker coi là lỗi vĩnh viễn, đánh dấu FAILED. |
| `not_json` | `200 OK` + Text thường (`text/plain`) | Phản hồi không phải JSON -> Worker coi là lỗi vĩnh viễn, đánh dấu FAILED. |
| `flaky` | Ngẫu nhiên `429`/`500` (xác suất `MOCK_ERROR_RATE`), còn lại `200` | Kiểm tra khả năng tự phục hồi của Worker dưới tải không ổn định. |
| `fail_n` | Trả `429` N lần đầu cho mỗi payload, từ lần N+1 trả `200 OK` | Giả lập lỗi tạm thời tự phục hồi sau N lần retry (mặc định N=2). |

> ⚠️ **Cảnh báo về mode `timeout`**: Mỗi lần gọi timeout khiến worker phải chờ trọn vẹn 60s. Với `MAX_RETRIES=3`, một job phải gọi 4 lần cộng thêm thời gian exponential backoff (1s + 2s + 4s = 7s), tổng cộng mất hơn **4 phút** mới vào DLQ. Vì worker chạy với `prefetch_count=1` nên worker sẽ bị chiếm dụng và chặn đứng (blocked) suốt thời gian đó. **TUYỆT ĐỐI KHÔNG dùng mode timeout trong quá trình Load Test.**

---

## 5. Thứ tự ưu tiên chọn Mode

Khi nhận request `POST /generate`, server xác định mode xử lý theo thứ tự từ cao xuống thấp:

1. **Tag ở đầu payload**: `[mock:<mode>]` hoặc `[mock:<mode>:<n>]` (ví dụ: `[mock:429] ...`, `[mock:fail_n:2] ...`, `[mock:slow:5] ...`).
   - **LƯU Ý QUAN TRỌNG: Tag PHẢI nằm ở ĐẦU payload, không có khoảng trắng hay bất kỳ ký tự nào phía trước.** Ví dụ chuỗi `" [mock:429] Dự báo"` có khoảng trắng đầu sẽ bị bỏ qua tag và xử lý như `success`.
   - Nếu tag chỉ định một mode không hợp lệ (gõ sai tên mode), server trả về lỗi `422 Unprocessable Entity` (`{"detail": "Unknown mock mode: <mode>"}`).
2. **Header `X-Mock-Mode`**: Dùng khi test trực tiếp bằng curl (ví dụ: `-H "X-Mock-Mode: 500"`, `-H "X-Mock-Mode: fail_n:3"`).
3. **Mode toàn cục**: Đặt qua `POST /admin/mode` (từ chối mode lạ với `422`).
4. **Biến môi trường**: `MOCK_MODE` (mặc định là `success`).

---

## 6. Bảng kết quả kỳ vọng khi test qua `POST /jobs`

*(Giả định cấu hình mặc định `MAX_RETRIES=3`, một job gọi Gemini tối đa 1 lần đầu + 3 lần retry = 4 lần).*

| Tag trong Payload Job | Trạng thái Job kết thúc | Chi tiết hành vi hệ thống |
|---|---|---|
| `[mock:fail_n:2] id=xxx ...` | `completed` | Thất bại 2 lần đầu (429), lần retry thứ 2 thành công (`retry_count=2`). |
| `[mock:fail_n:3] id=xxx ...` | `completed` | Thất bại 3 lần đầu (429), lần retry thứ 3 thành công (`retry_count=3`). |
| `[mock:fail_n:4] id=xxx ...` | `failed` (vào DLQ) | Thất bại cả 4 lần gọi (1 lần đầu + 3 lần retry), chuyển vào `jobs.dlq`, mock bị gọi đúng 4 lần. |
| `[mock:429] ...` hoặc `[mock:500] ...` | `failed` (vào DLQ) | Lỗi tạm thời liên tục, retry 3 lần rồi chuyển vào DLQ. |
| `[mock:400] ...`, `[mock:bad_json] ...`, `[mock:not_json] ...` | `failed` ngay | Lỗi vĩnh viễn -> Đánh dấu FAILED ngay lập tức, **không retry, không vào DLQ**. |

**Cách kiểm chứng**: Gọi `GET /admin/stats`, trường `max_calls_per_payload` cho bất kỳ job nào phải luôn `<= 4` (không bao giờ vượt quá `MAX_RETRIES + 1`).

---

## 7. Quản trị & Thống kê (`/admin/*`)

### Đổi Mode toàn cục lúc runtime (`POST /admin/mode`)
```bash
# Đổi mode toàn cục
Invoke-RestMethod -Uri http://localhost:9000/admin/mode -Method POST -ContentType "application/json" -Body '{"mode":"500"}'

# fail_n toàn cục với N=3
Invoke-RestMethod -Uri http://localhost:9000/admin/mode -Method POST -ContentType "application/json" -Body '{"mode":"fail_n","n":3}'

# Khôi phục về bình thường
Invoke-RestMethod -Uri http://localhost:9000/admin/mode -Method POST -ContentType "application/json" -Body '{"mode":"default"}'

# Xem thống kê, reset
Invoke-RestMethod http://localhost:9000/admin/stats
Invoke-RestMethod -Uri http://localhost:9000/admin/reset -Method POST

Phản hồi mẫu:
```json
{
  "total_requests": 15,
  "distinct_payloads": 2,
  "max_calls_per_payload": 3,
  "top_payloads": {
    "[mock:fail_n:2] id=req_001 Du bao ton kho": 3,
    "[mock:429] Dự báo tồn kho SKU-002": 1
  },
  "global_mode": "success",
  "global_fail_n": 2
}
```

### Reset bộ đếm thống kê (`POST /admin/reset`)
```bash
curl.exe -i -X POST http://localhost:9000/admin/reset
```
> 💡 **Nhắc nhở quan trọng**: Hãy gọi `POST /admin/reset` giữa các lần test, vì bộ đếm `fail_n` được lưu trong bộ nhớ theo chuỗi `payload`. Nếu chạy lại đúng chuỗi `payload` cũ mà không reset, request sẽ vượt qua số lần lỗi N và thành công ngay lập tức!

### Kiểm tra Health Check (`GET /health`)
```bash
curl.exe http://localhost:9000/health
```

---

## 8. Lưu ý khi Load Test (Locust) với `fail_n`

Mode `fail_n` đếm số lần thất bại **theo nội dung payload**. Vì khi Worker retry, nó gửi lại chính xác cùng một `payload`:

- Nếu nhiều Locust virtual user gửi cùng một chuỗi `payload` (ví dụ `"Du bao"`), bộ đếm `fail_n` sẽ bị cộng dồn chung giữa các user dẫn đến hành vi không như mong muốn.
- **Giải pháp**: Mỗi request tạo bởi Locust cần đính kèm một ID duy nhất (ví dụ UUID hoặc timestamp) vào payload:
  ```python
  import uuid
  unique_id = uuid.uuid4().hex[:8]
  payload = f"[mock:fail_n:2] id={unique_id} Du bao mat hang {sku}"
  ```
  Nhờ đó, mỗi chuỗi retry của từng job sẽ có bộ đếm `fail_n` độc lập và chính xác tuyệt đối.
