"""
Chat and conversation data models for AI Game Generator.
Defines structures for conversational interface and message handling.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from ..utils.constants import MessageType, ModificationType


class ChatMessage(BaseModel):
    """Individual chat message model."""

    id: str = Field(description="Unique message identifier")
    session_id: str = Field(description="Session ID this message belongs to")
    type: MessageType = Field(description="Type of message")
    content: str = Field(description="Message content")
    role: str = Field(description="Message role (user, assistant, system)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional message metadata"
    )

    @validator("role")
    def validate_role(cls, v):
        valid_roles = {"user", "assistant", "system"}
        if v not in valid_roles:
            raise ValueError(f"Role must be one of {valid_roles}")
        return v

    @validator("content")
    def validate_content(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(v) > 10000:
            raise ValueError("Message content too long (max 10000 characters)")
        return v.strip()


class ChatRequest(BaseModel):
    """Request model for sending chat messages."""

    message: str = Field(min_length=1, max_length=5000, description="User message content")
    session_id: str = Field(description="Session ID for the conversation")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context for the message"
    )


class ConversationContext(BaseModel):
    """Context for maintaining conversation state."""

    session_id: str = Field(description="Session identifier")
    current_game_state: Optional[Dict[str, Any]] = Field(
        default=None, description="Current state of the game being discussed"
    )
    conversation_history: List[ChatMessage] = Field(
        default_factory=list, description="Recent conversation messages"
    )
    user_intent: Optional[str] = Field(default=None, description="Detected user intent")
    modification_type: Optional[ModificationType] = Field(
        default=None, description="Type of modification being discussed"
    )
    active_features: List[str] = Field(
        default_factory=list, description="Currently active game features"
    )
    conversation_stage: str = Field(
        default="initial", description="Current stage of the conversation"
    )
    last_activity: datetime = Field(
        default_factory=datetime.utcnow, description="Last conversation activity"
    )
