from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import setup_logging

logger = setup_logging()


@dataclass
class ErrorDetail:
    code: str
    message: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str | int):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": str(identifier)},
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            code="RATE_LIMITED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


def create_error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError",
        extra={
            "code": exc.code,
            "error_message": exc.message,
            "details": exc.details,
            "path": request.url.path,
        },
    )
    return create_error_response(exc.code, exc.message, exc.status_code, exc.details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        "HTTPException",
        extra={"status_code": exc.status_code, "detail": exc.detail, "path": request.url.path},
    )
    return create_error_response(
        "HTTP_ERROR",
        str(exc.detail),
        exc.status_code,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(
        "ValidationError",
        extra={"errors": exc.errors(), "path": request.url.path},
    )
    return create_error_response(
        "VALIDATION_ERROR",
        "Request validation failed",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        {"errors": exc.errors()},
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: PydanticValidationError
) -> JSONResponse:
    logger.warning(
        "PydanticValidationError",
        extra={"errors": exc.errors(), "path": request.url.path},
    )
    return create_error_response(
        "VALIDATION_ERROR",
        "Data validation failed",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        {"errors": exc.errors()},
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.error(
        "IntegrityError",
        extra={"error": str(exc.orig), "path": request.url.path},
    )
    return create_error_response(
        "CONFLICT",
        "Resource already exists or constraint violation",
        status.HTTP_409_CONFLICT,
    )


async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error(
        "OperationalError",
        extra={"error": str(exc.orig), "path": request.url.path},
    )
    return create_error_response(
        "DATABASE_ERROR",
        "Database operation failed",
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "UnhandledException",
        extra={"error": str(exc), "path": request.url.path},
    )
    return create_error_response(
        "INTERNAL_ERROR",
        "An unexpected error occurred",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
