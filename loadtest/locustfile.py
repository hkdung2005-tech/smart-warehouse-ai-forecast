import uuid
import requests
from locust import HttpUser, task, between, events

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Tự động reset Mock Gemini trước mỗi lần chạy test (mức tải 1x, 10x, v.v.)
    để đảm bảo số liệu đếm số lượng request của Mock được chính xác.
    """
    try:
        response = requests.post("http://localhost:9000/admin/reset", timeout=5)
        response.raise_for_status()
        print("Đã reset Mock Gemini thành công trước khi bắt đầu test.")
    except Exception as e:
        print(f"Cảnh báo: Không thể gọi Mock Gemini reset ({e}). Vui lòng kiểm tra lại nếu test dùng Mock.")

class WarehouseUser(HttpUser):
    # Thời gian chờ giữa các request của một user
    wait_time = between(0.1, 0.5)

    @task
    def create_job(self):
        # Dùng UUID đầy đủ để tránh trùng lặp khi chạy hàng chục nghìn request (Issue #5)
        unique_id = str(uuid.uuid4())
        payload = f"id={unique_id} Load testing forecast demand for SKU-{unique_id}"
        
        # Dùng catch_response=True để tự đánh giá kết quả (Issue #1)
        with self.client.post(
            "/jobs",
            json={"payload": payload},
            name="POST /jobs",
            catch_response=True
        ) as response:
            if response.status_code == 202:
                try:
                    data = response.json()
                    if "job_id" in data:
                        response.success()
                    else:
                        response.failure(f"Status 202 nhưng không có job_id: {response.text}")
                except ValueError:
                    response.failure(f"Status 202 nhưng body không phải JSON: {response.text}")
            else:
                response.failure(f"HTTP Status: {response.status_code}")
