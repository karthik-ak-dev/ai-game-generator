"""
Custom exceptions for enterprise error handling.
Provides structured exception hierarchy for different error types.
"""

from typing import Any, Dict, Optional


class BaseApplicationError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseApplicationError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


class BusinessLogicError(BaseApplicationError):
    """Raised when business logic rules are violated."""

    def __init__(self, message: str, error_code: str = "BUSINESS_LOGIC_ERROR"):
        super().__init__(message=message, error_code=error_code)


class NotFoundError(BaseApplicationError):
    """Raised when requested resource is not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class UnauthorizedError(BaseApplicationError):
    """Raised when user is not authorized for the operation."""

    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message=message, error_code="UNAUTHORIZED")


class RateLimitError(BaseApplicationError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, error_code="RATE_LIMIT_EXCEEDED")
