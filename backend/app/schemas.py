"""
Common response schemas for API endpoints.
"""
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """
    Unified API response format.
    
    Attributes:
        code: 0 for success, non-zero for error codes
        message: Human-readable message
        data: Response payload
    """
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """Error response model for OpenAPI documentation."""
    code: int
    message: str
    data: Optional[Any] = None


def success_response(data: Any = None, message: str = "success") -> dict:
    """Create a success response dict."""
    return {
        "code": 0,
        "message": message,
        "data": data
    }


def error_response(code: int, message: str, data: Any = None) -> dict:
    """Create an error response dict."""
    return {
        "code": code,
        "message": message,
        "data": data
    }
