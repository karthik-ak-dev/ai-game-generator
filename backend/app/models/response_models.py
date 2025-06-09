"""
Standardized response models for AI Game Generator API.
Provides consistent response structures across all endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..utils.constants import HTTP_STATUS


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(description="Whether the request was successful")
    message: str = Field(description="Human-readable response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(default=None, description="Unique request identifier")


class SuccessResponse(BaseResponse):
    """Standard success response model."""

    success: bool = Field(default=True)
    data: Optional[Any] = Field(default=None, description="Response data payload")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(description="Error code identifier")
    message: str = Field(description="Error message")
    field: Optional[str] = Field(default=None, description="Field that caused the error")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error context")


class ErrorResponse(BaseResponse):
    """Standard error response model."""

    success: bool = Field(default=False)
    error: ErrorDetail = Field(description="Error details")
    status_code: int = Field(description="HTTP status code")

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "Validation failed",
                "timestamp": "2023-12-07T10:30:00Z",
                "request_id": "req_123456789",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed",
                    "field": "prompt",
                    "details": {"min_length": 10},
                },
                "status_code": 422,
            }
        }


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field-specific errors."""

    validation_errors: List[ErrorDetail] = Field(
        default_factory=list, description="List of validation errors"
    )


class PaginationMetadata(BaseModel):
    """Pagination information for list responses."""

    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Number of items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_previous: bool = Field(description="Whether there is a previous page")


class PaginatedResponse(SuccessResponse):
    """Response model for paginated data."""

    data: List[Any] = Field(default_factory=list, description="List of items for current page")
    pagination: PaginationMetadata = Field(description="Pagination information")


class GameGenerationResponse(SuccessResponse):
    """Response model for game generation requests."""

    data: Dict[str, Any] = Field(default_factory=dict, description="Game generation data")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Game generated successfully",
                "timestamp": "2023-12-07T10:30:00Z",
                "request_id": "req_123456789",
                "data": {
                    "session_id": "session_abc123",
                    "game_code": "<html>...</html>",
                    "game_type": "platformer",
                    "generation_time": 5.2,
                    "version": 1,
                },
            }
        }


class ChatMessageResponse(SuccessResponse):
    """Response model for chat message processing."""

    data: Dict[str, Any] = Field(default_factory=dict, description="Chat response data")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Message processed successfully",
                "timestamp": "2023-12-07T10:30:00Z",
                "data": {
                    "response": "I've made the character red as requested!",
                    "modifications_applied": ["character_color_change"],
                    "game_updated": True,
                    "processing_time": 2.1,
                },
            }
        }


class SessionResponse(SuccessResponse):
    """Response model for session operations."""

    data: Dict[str, Any] = Field(default_factory=dict, description="Session data")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Session retrieved successfully",
                "timestamp": "2023-12-07T10:30:00Z",
                "data": {
                    "session_id": "session_abc123",
                    "status": "active",
                    "created_at": "2023-12-07T10:00:00Z",
                    "last_activity": "2023-12-07T10:29:00Z",
                    "game_count": 1,
                    "message_count": 5,
                },
            }
        }


class TemplateResponse(SuccessResponse):
    """Response model for template operations."""

    data: Dict[str, Any] = Field(default_factory=dict, description="Template data")


class HealthCheckResponse(BaseResponse):
    """Health check response model."""

    status: str = Field(description="Service health status")
    services: Dict[str, Dict[str, Any]] = Field(description="Individual service statuses")
    version: str = Field(description="Application version")
    uptime: float = Field(description="Service uptime in seconds")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "All services healthy",
                "timestamp": "2023-12-07T10:30:00Z",
                "status": "healthy",
                "services": {
                    "redis": {"status": "healthy", "response_time": 0.01},
                    "openai": {"status": "healthy", "response_time": 0.15},
                },
                "version": "1.0.0",
                "uptime": 3600.5,
            }
        }


class WebSocketResponse(BaseModel):
    """WebSocket message response model."""

    type: str = Field(description="Message type")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = Field(default=None, description="Session identifier")

    class Config:
        schema_extra = {
            "example": {
                "type": "game_update",
                "data": {
                    "game_code": "<html>...</html>",
                    "modifications": ["character_color_change"],
                },
                "timestamp": "2023-12-07T10:30:00Z",
                "session_id": "session_abc123",
            }
        }


class StreamingResponse(BaseModel):
    """Response model for streaming data."""

    chunk_id: int = Field(description="Chunk sequence number")
    total_chunks: Optional[int] = Field(default=None, description="Total expected chunks")
    data: str = Field(description="Chunk data")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")

    class Config:
        schema_extra = {
            "example": {
                "chunk_id": 1,
                "total_chunks": 5,
                "data": "Generating game components...",
                "is_final": False,
            }
        }


class MetricsResponse(SuccessResponse):
    """Response model for performance metrics."""

    data: Dict[str, Union[int, float, str]] = Field(
        default_factory=dict, description="Metrics data"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Metrics retrieved successfully",
                "timestamp": "2023-12-07T10:30:00Z",
                "data": {
                    "total_sessions": 1250,
                    "active_sessions": 45,
                    "games_generated": 3421,
                    "avg_generation_time": 4.2,
                    "avg_response_time": 0.15,
                    "cpu_usage": 65.5,
                    "memory_usage": 78.2,
                },
            }
        }


# Utility functions for creating standardized responses


def create_success_response(
    message: str,
    data: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> SuccessResponse:
    """Create a standardized success response."""
    return SuccessResponse(message=message, data=data, metadata=metadata, request_id=request_id)


def create_error_response(
    message: str,
    error_code: str,
    status_code: int = HTTP_STATUS["INTERNAL_SERVER_ERROR"],
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a standardized error response."""
    error_detail = ErrorDetail(code=error_code, message=message, field=field, details=details)

    return ErrorResponse(
        message=message, error=error_detail, status_code=status_code, request_id=request_id
    )


def create_validation_error_response(
    message: str, validation_errors: List[ErrorDetail], request_id: Optional[str] = None
) -> ValidationErrorResponse:
    """Create a validation error response."""
    return ValidationErrorResponse(
        message=message,
        error=ErrorDetail(code="VALIDATION_ERROR", message=message),
        status_code=HTTP_STATUS["UNPROCESSABLE_ENTITY"],
        validation_errors=validation_errors,
        request_id=request_id,
    )


def create_paginated_response(
    items: List[Any],
    page: int,
    page_size: int,
    total_items: int,
    message: str = "Data retrieved successfully",
    request_id: Optional[str] = None,
) -> PaginatedResponse:
    """Create a paginated response."""
    total_pages = (total_items + page_size - 1) // page_size

    pagination = PaginationMetadata(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

    return PaginatedResponse(
        message=message, data=items, pagination=pagination, request_id=request_id
    )
