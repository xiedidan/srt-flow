"""
Custom exceptions and global exception handlers.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.schemas import error_response


class AppException(Exception):
    """
    Base application exception.
    
    Attributes:
        code: Error code (non-zero)
        message: Error message
        status_code: HTTP status code
    """
    def __init__(
        self, 
        code: int = 1, 
        message: str = "An error occurred",
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found exception."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            code=404,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )


class ValidationError(AppException):
    """Validation error exception."""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(
            code=422,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class ConfigError(AppException):
    """Configuration error exception."""
    def __init__(self, message: str = "Configuration error"):
        super().__init__(
            code=500,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class TaskError(AppException):
    """Task execution error exception."""
    def __init__(self, message: str = "Task execution failed"):
        super().__init__(
            code=1001,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for AppException."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message)
    )


async def http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handler for HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.status_code, str(exc.detail))
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """Handler for request validation errors."""
    errors = exc.errors()
    message = "; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in errors])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(422, f"Validation error: {message}")
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(500, "Internal server error")
    )
