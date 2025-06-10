"""
Core response models for API standardization.
Provides consistent response formats across all endpoints.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    """Standard success response model."""

    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(description="Human-readable success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "status": "completed"},
                "timestamp": "2023-12-07T10:30:00Z",
                "request_id": "req_123456789",
            }
        }


# Utility functions for response creation


def create_success_response(
    message: str, data: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None
) -> SuccessResponse:
    """Create a standardized success response."""
    return SuccessResponse(message=message, data=data, request_id=request_id)
