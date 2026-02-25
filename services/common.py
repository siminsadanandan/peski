import re


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def enforce_5mb(content: bytes, max_bytes: int = 5 * 1024 * 1024):
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max is {max_bytes} bytes (~5MB).")


def safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)[:180]
