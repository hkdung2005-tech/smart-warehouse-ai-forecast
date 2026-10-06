FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PORT=9000 \
  MOCK_MODE=success \
  MOCK_DELAY=2.0 \
  MOCK_ERROR_RATE=0.3 \
  MOCK_FAIL_COUNT=2

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','9000'))" || exit 1

CMD ["sh", "-c", "exec uvicorn mock_server:app --host 0.0.0.0 --port ${PORT}"]
