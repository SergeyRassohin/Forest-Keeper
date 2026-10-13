from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": {}}}
