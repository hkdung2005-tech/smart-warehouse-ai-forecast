FROM python:3.12-slim

# Không cần virtualenv bên trong container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cài dependencies trước (cache layer nếu requirements.txt không đổi)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Hot-reload trong dev (volume mount ở docker-compose sẽ override code)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
