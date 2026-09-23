from __future__ import annotations


class LabError(Exception):
    """User-facing error with an optional fix hint."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\n  {self.hint}"
        return self.message
