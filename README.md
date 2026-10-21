# Smart Warehouse - AI Forecast
Giai đoạn 1 (Giữa kỳ): Trình bày kiến trúc Prototype RabbitMQ, Docker, Locust load test x10 requests.
Giai đoạn 2 (Cuối kỳ): Cấu trúc tổng thể với Next.js/Nuxt, Go/FastAPI, PostgreSQL và cách gọi Gemini API.

## Cách chạy

```powershell
cp .env.example .env
docker compose up --build
```

Sau khi các dịch vụ khởi động:

- API docs (Swagger): http://localhost:8000/docs
- RabbitMQ Management UI: http://localhost:15672
- Mock Gemini: http://localhost:9000

Link deploy: https://smart-warehouse-ai-forecast.onrender.com/

## Tài liệu

Xem thư mục [`docs/`](docs/README.md) (SRS, User Stories, API Contract, Test Cases...).
