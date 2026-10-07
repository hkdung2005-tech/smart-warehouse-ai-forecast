import uuid
from locust import HttpUser, task, between

class WarehouseUser(HttpUser):
    # Thời gian chờ giữa các request của một user (nếu muốn bắn liên tục thì để 0)
    wait_time = between(0.1, 0.5)

    @task
    def create_job(self):
        # Yêu cầu của Mock Gemini: id=<mã duy nhất> nằm trong payload để đếm request chính xác
        unique_id = str(uuid.uuid4())[:8]
        payload = f"id={unique_id} Load testing forecast demand for SKU-{unique_id}"
        
        self.client.post(
            "/jobs",
            json={"payload": payload},
            name="POST /jobs"
        )
