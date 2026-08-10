from __future__ import annotations


class BookStackAPIError(RuntimeError):
    def __init__(self, status: int, message: str, payload: object | None = None) -> None:
        super().__init__(f"BookStack API error {status}: {message}")
        self.status = status
        self.message = message
        self.payload = payload
