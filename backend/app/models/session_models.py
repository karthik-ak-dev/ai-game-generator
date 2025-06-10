"""
Session management data models for AI Game Generator.
Defines structures for session creation, state tracking, and lifecycle management.
"""

# Standard library imports
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
from pydantic import BaseModel, Field, validator

# Local application imports
from ..utils.constants import SessionStatus


class SessionCreationRequest(BaseModel):
    """Request model for creating a new session."""

    user_id: Optional[str] = Field(default=None, description="Optional user identifier")
    initial_prompt: Optional[str] = Field(default=None, description="Initial game description")
    client_info: Optional[Dict[str, Any]] = Field(default=None, description="Client information")
    preferences: Optional[Dict[str, Any]] = Field(default=None, description="User preferences")

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user_123",
                "initial_prompt": "Create a platformer game",
                "client_info": {"user_agent": "Mozilla/5.0...", "ip_address": "192.168.1.1"},
                "preferences": {"preferred_engine": "phaser", "difficulty": "beginner"},
            }
        }


class SessionInfo(BaseModel):
    """Core session information."""

    session_id: str = Field(description="Unique session identifier")
    status: SessionStatus = Field(description="Current session status")
    created_at: datetime = Field(description="Session creation timestamp")
    last_activity: datetime = Field(description="Last activity timestamp")
    expires_at: datetime = Field(description="Session expiration timestamp")
    user_id: Optional[str] = Field(default=None, description="Associated user ID")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "status": "active",
                "created_at": "2023-12-07T10:00:00Z",
                "last_activity": "2023-12-07T10:30:00Z",
                "expires_at": "2023-12-07T14:00:00Z",
                "user_id": "user_123",
                "ip_address": "192.168.1.1",
            }
        }


class SessionState(BaseModel):
    """Complete session state including all session data."""

    session_info: SessionInfo = Field(description="Basic session information")
    current_game_id: Optional[str] = Field(default=None, description="Currently active game ID")
    games: List[str] = Field(default_factory=list, description="List of game IDs in this session")
    conversation_messages: int = Field(default=0, description="Total conversation messages")
    modifications_made: int = Field(default=0, description="Total modifications made")
    generation_count: int = Field(default=0, description="Number of games generated")
    error_count: int = Field(default=0, description="Number of errors encountered")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional session metadata"
    )

    @validator("conversation_messages", "modifications_made", "generation_count", "error_count")
    def validate_counts(cls, v):
        if v < 0:
            raise ValueError("Counts cannot be negative")
        return v

    class Config:
        schema_extra = {
            "example": {
                "session_info": {
                    "session_id": "session_abc123",
                    "status": "active",
                    "created_at": "2023-12-07T10:00:00Z",
                },
                "current_game_id": "game_xyz789",
                "games": ["game_xyz789"],
                "conversation_messages": 8,
                "modifications_made": 3,
                "generation_count": 1,
                "error_count": 0,
                "preferences": {"engine": "phaser", "difficulty": "intermediate"},
            }
        }
