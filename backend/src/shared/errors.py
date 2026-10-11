"""Типизированные ошибки и их HTTP-представление: {"error": {"code", "message", "details"}}."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Ошибка с кодом для клиента. Сообщение — понятное человеку, код — стабильный."""

    status_code = 400

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ForbiddenError(AppError):
    status_code = 403


class UnauthorizedError(AppError):
    status_code = 401


class ValidationFailedError(AppError):
    status_code = 422


class UpstreamUnavailableError(AppError):
    """Другой сервис не ответил: операция ждёт, а не проходит молча."""

    status_code = 503


class ConfigurationError(RuntimeError):
    """Сервис нельзя запускать с такой конфигурацией."""


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
