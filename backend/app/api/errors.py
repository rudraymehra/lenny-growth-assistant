"""Structured error handling: every non-2xx response is the same envelope
{"error": {"code", "message", "request_id"}} so clients handle one shape."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ProviderUnavailableError(AppError):
    status_code = 503
    code = "provider_unavailable"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
        )
        return error_response(request, 422, "validation_error", detail)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return error_response(request, 500, "internal_error", "An unexpected error occurred.")
