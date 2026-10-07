FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GEMINI_API_URL=http://localhost:9000/generate

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
COPY worker/requirements.txt worker/requirements.txt
COPY gemini/requirements.txt gemini/requirements.txt
RUN pip install --no-cache-dir \
    -r api/requirements.txt \
    -r worker/requirements.txt \
    -r gemini/requirements.txt

COPY api/ api/
COPY worker/ worker/
COPY gemini/ gemini/
COPY start.sh start.sh
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

EXPOSE 8000 9000

CMD ["./start.sh"]
