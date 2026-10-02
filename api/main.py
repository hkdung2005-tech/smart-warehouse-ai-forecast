from fastapi import FastAPI

app = FastAPI(title="Smart Warehouse AI Forecast API")


@app.get("/health")
def health():
    return {"status": "ok"}