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


class SessionMetrics(BaseModel):
    """Performance and usage metrics for a session."""

    session_id: str = Field(description="Session identifier")
    duration_seconds: float = Field(description="Total session duration")
    total_requests: int = Field(description="Total API requests made")
    successful_requests: int = Field(description="Number of successful requests")
    failed_requests: int = Field(description="Number of failed requests")
    avg_response_time: float = Field(description="Average response time in seconds")
    total_tokens_used: int = Field(description="Total AI tokens consumed")
    bandwidth_used: int = Field(description="Total bandwidth used in bytes")
    peak_memory_usage: Optional[float] = Field(default=None, description="Peak memory usage in MB")

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "duration_seconds": 1800.5,
                "total_requests": 15,
                "successful_requests": 14,
                "failed_requests": 1,
                "avg_response_time": 2.3,
                "total_tokens_used": 3450,
                "bandwidth_used": 245760,
                "peak_memory_usage": 128.5,
            }
        }


class SessionActivity(BaseModel):
    """Individual session activity record."""

    session_id: str = Field(description="Session identifier")
    activity_type: str = Field(description="Type of activity")
    timestamp: datetime = Field(description="Activity timestamp")
    details: Dict[str, Any] = Field(description="Activity details")
    duration: Optional[float] = Field(default=None, description="Activity duration in seconds")
    success: bool = Field(description="Whether activity was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")

    @validator("activity_type")
    def validate_activity_type(cls, v):
        valid_types = {
            "session_created",
            "game_generated",
            "game_modified",
            "message_sent",
            "template_loaded",
            "session_expired",
            "error_occurred",
            "session_terminated",
        }
        if v not in valid_types:
            raise ValueError(f"Activity type must be one of {valid_types}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "activity_type": "game_modified",
                "timestamp": "2023-12-07T10:30:00Z",
                "details": {"modification": "character_color_change", "game_id": "game_xyz789"},
                "duration": 2.1,
                "success": True,
            }
        }


class SessionCleanupTask(BaseModel):
    """Task for cleaning up expired sessions."""

    task_id: str = Field(description="Cleanup task identifier")
    scheduled_at: datetime = Field(description="When cleanup is scheduled")
    sessions_to_cleanup: List[str] = Field(description="Session IDs to clean up")
    cleanup_type: str = Field(description="Type of cleanup (expired, terminated, etc.)")
    status: str = Field(default="pending", description="Cleanup task status")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    results: Optional[Dict[str, Any]] = Field(default=None, description="Cleanup results")

    @validator("cleanup_type")
    def validate_cleanup_type(cls, v):
        valid_types = {"expired", "terminated", "idle", "error", "manual"}
        if v not in valid_types:
            raise ValueError(f"Cleanup type must be one of {valid_types}")
        return v

    @validator("status")
    def validate_status(cls, v):
        valid_statuses = {"pending", "running", "completed", "failed"}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v


class SessionSummary(BaseModel):
    """Summary of session activity and outcomes."""

    session_id: str = Field(description="Session identifier")
    duration_minutes: float = Field(description="Total session duration in minutes")
    games_created: int = Field(description="Number of games created")
    total_modifications: int = Field(description="Total modifications made")
    conversation_turns: int = Field(description="Number of conversation turns")
    user_satisfaction: Optional[float] = Field(default=None, description="User satisfaction score")
    final_status: SessionStatus = Field(description="Final session status")
    main_activities: List[str] = Field(description="Main activities performed")
    achievements: List[str] = Field(default_factory=list, description="Session achievements")
    issues_encountered: List[str] = Field(default_factory=list, description="Issues during session")

    @validator("user_satisfaction")
    def validate_satisfaction(cls, v):
        if v is not None and (v < 0 or v > 10):
            raise ValueError("User satisfaction must be between 0 and 10")
        return v

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "duration_minutes": 30.5,
                "games_created": 1,
                "total_modifications": 5,
                "conversation_turns": 10,
                "user_satisfaction": 8.5,
                "final_status": "completed",
                "main_activities": ["game_creation", "character_modification", "sound_addition"],
                "achievements": ["first_game_created", "successful_modifications"],
                "issues_encountered": [],
            }
        }


class SessionConfiguration(BaseModel):
    """Configuration settings for a session."""

    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    max_games_per_session: int = Field(default=10, description="Maximum games per session")
    max_conversation_length: int = Field(default=100, description="Maximum conversation messages")
    auto_save_interval: int = Field(default=300, description="Auto-save interval in seconds")
    enable_analytics: bool = Field(default=True, description="Whether to collect analytics")
    preferred_engine: Optional[str] = Field(default=None, description="Preferred game engine")
    default_difficulty: str = Field(default="beginner", description="Default difficulty level")

    @validator("session_timeout")
    def validate_timeout(cls, v):
        if v < 300 or v > 86400:  # 5 minutes to 24 hours
            raise ValueError("Session timeout must be between 300 and 86400 seconds")
        return v

    @validator("max_games_per_session")
    def validate_max_games(cls, v):
        if v < 1 or v > 50:
            raise ValueError("Max games per session must be between 1 and 50")
        return v


class SessionBackup(BaseModel):
    """Backup data for session recovery."""

    session_id: str = Field(description="Session identifier")
    backup_timestamp: datetime = Field(description="Backup creation timestamp")
    session_data: Dict[str, Any] = Field(description="Complete session data")
    game_states: List[Dict[str, Any]] = Field(description="All game states")
    conversation_history: List[Dict[str, Any]] = Field(description="Conversation backup")
    backup_size: int = Field(description="Backup size in bytes")
    compression_used: bool = Field(default=False, description="Whether backup is compressed")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "backup_timestamp": "2023-12-07T10:30:00Z",
                "backup_size": 524288,
                "compression_used": True,
            }
        }
