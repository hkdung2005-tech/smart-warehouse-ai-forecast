import requests

from worker.config import GEMINI_API_KEY, GEMINI_API_URL


class GeminiError(Exception):
    def __init__(self, message: str, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def generate(payload: str) -> str:
    headers = {"Content-Type": "application/json"}
    if GEMINI_API_KEY:
        headers["Authorization"] = f"Bearer {GEMINI_API_KEY}"
    try:
        response = requests.post(GEMINI_API_URL, json={"payload": payload}, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise GeminiError(str(exc)) from exc
    if not response.ok:
        raise GeminiError(response.text or f"Gemini returned HTTP {response.status_code}", response.status_code)
    try:
        data = response.json()
    except ValueError as exc:
        raise GeminiError("Gemini response must be JSON", response.status_code) from exc
    result = data.get("result")
    if not isinstance(result, str):
        raise GeminiError("Gemini response must contain a string 'result'", response.status_code)
    return result
