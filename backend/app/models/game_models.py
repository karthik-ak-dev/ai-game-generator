"""
Game-related data models for AI Game Generator.
Defines structures for game creation, modification, and state management.
"""

# Standard library imports
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
from pydantic import BaseModel, Field, validator

from ..utils.constants import GAME_ENGINES, GameType, GenerationStatus, ModificationType


class GameGenerationRequest(BaseModel):
    """Request model for creating a new game."""

    prompt: str = Field(
        min_length=10,
        max_length=5000,
        description="Natural language description of the game to create",
    )
    game_type: Optional[GameType] = Field(
        default=None, description="Specific game type (auto-detected if not provided)"
    )
    engine: Optional[str] = Field(
        default="phaser", description="Game engine to use (phaser, three, p5)"
    )
    difficulty: Optional[str] = Field(default="beginner", description="Target difficulty level")
    features: Optional[List[str]] = Field(default=None, description="Specific features to include")
    template_id: Optional[str] = Field(default=None, description="Base template to start from")
    session_id: Optional[str] = Field(
        default=None, description="Existing session ID (creates new if not provided)"
    )

    @validator("engine")
    def validate_engine(cls, v):
        if v not in GAME_ENGINES:
            raise ValueError(f"Engine must be one of {list(GAME_ENGINES.keys())}")
        return v

    @validator("difficulty")
    def validate_difficulty(cls, v):
        valid_difficulties = {"beginner", "intermediate", "advanced", "expert"}
        if v not in valid_difficulties:
            raise ValueError(f"Difficulty must be one of {valid_difficulties}")
        return v

    @validator("features")
    def validate_features(cls, v):
        if v and len(v) > 20:
            raise ValueError("Maximum 20 features allowed")
        return v

    class Config:
        schema_extra = {
            "example": {
                "prompt": (
                    "Create a space shooter where the player controls a ship "
                    "and destroys asteroids"
                ),
                "game_type": "shooter",
                "engine": "phaser",
                "difficulty": "intermediate",
                "features": ["powerups", "particle_effects", "sound"],
                "session_id": None,
            }
        }


class GameModificationRequest(BaseModel):
    """Request model for modifying an existing game."""

    message: str = Field(
        min_length=5,
        max_length=2000,
        description="Natural language description of the modification",
    )
    session_id: str = Field(description="Session ID containing the game to modify")
    modification_type: Optional[ModificationType] = Field(
        default=None, description="Type of modification (auto-detected if not provided)"
    )
    preserve_features: Optional[List[str]] = Field(
        default=None, description="Features that must be preserved during modification"
    )
    priority: Optional[str] = Field(
        default="normal", description="Modification priority (low, normal, high)"
    )

    @validator("priority")
    def validate_priority(cls, v):
        valid_priorities = {"low", "normal", "high"}
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of {valid_priorities}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "message": "Make the player character red instead of blue",
                "session_id": "session_abc123",
                "modification_type": "visual_change",
                "preserve_features": ["collision_detection", "scoring"],
                "priority": "normal",
            }
        }


class GameMetadata(BaseModel):
    """Metadata for a generated game."""

    title: Optional[str] = Field(default=None, description="Game title")
    description: Optional[str] = Field(default=None, description="Game description")
    game_type: GameType = Field(description="Type of game")
    engine: str = Field(description="Game engine used")
    difficulty: str = Field(description="Difficulty level")
    features: List[str] = Field(default_factory=list, description="Game features")
    controls: Dict[str, str] = Field(default_factory=dict, description="Game controls")
    objectives: List[str] = Field(default_factory=list, description="Game objectives")
    estimated_playtime: Optional[int] = Field(
        default=None, description="Estimated playtime in minutes"
    )
    tags: List[str] = Field(default_factory=list, description="Game tags")

    class Config:
        schema_extra = {
            "example": {
                "title": "Space Asteroid Hunter",
                "description": (
                    "Navigate your ship through an asteroid field " "while collecting powerups"
                ),
                "game_type": "shooter",
                "engine": "phaser",
                "difficulty": "intermediate",
                "features": ["powerups", "particle_effects", "collision_detection"],
                "controls": {"arrow_keys": "Move ship", "spacebar": "Shoot"},
                "objectives": [
                    "Destroy asteroids",
                    "Collect powerups",
                    "Achieve high score",
                ],
                "estimated_playtime": 10,
                "tags": ["action", "arcade", "space"],
            }
        }


class GameVersion(BaseModel):
    """Version information for a game."""

    version: int = Field(description="Version number")
    created_at: datetime = Field(description="Version creation timestamp")
    modification_summary: Optional[str] = Field(default=None, description="Summary of changes")
    modifications_applied: List[str] = Field(
        default_factory=list, description="List of modifications"
    )
    code_size: int = Field(description="Size of game code in bytes")
    generation_time: float = Field(description="Time taken to generate this version")
    is_current: bool = Field(default=False, description="Whether this is the current version")
    parent_version: Optional[int] = Field(default=None, description="Previous version number")

    class Config:
        schema_extra = {
            "example": {
                "version": 3,
                "created_at": "2023-12-07T10:30:00Z",
                "modification_summary": "Changed character color and added coins",
                "modifications_applied": ["character_color_change", "coin_collection_system"],
                "code_size": 15420,
                "generation_time": 2.3,
                "is_current": True,
                "parent_version": 2,
            }
        }


class GameState(BaseModel):
    """Complete state of a game including code and metadata."""

    session_id: str = Field(description="Session ID")
    game_id: str = Field(description="Unique game identifier")
    code: str = Field(description="Complete HTML game code")
    metadata: GameMetadata = Field(description="Game metadata")
    current_version: int = Field(description="Current version number")
    versions: List[GameVersion] = Field(default_factory=list, description="Version history")
    status: GenerationStatus = Field(description="Current game status")
    created_at: datetime = Field(description="Game creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    conversation_context: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conversation history for this game"
    )

    @validator("code")
    def validate_code(cls, v):
        if len(v) > 2 * 1024 * 1024:  # 2MB limit
            raise ValueError("Game code too large (max 2MB)")
        return v

    @validator("conversation_context")
    def validate_conversation_context(cls, v):
        if len(v) > 100:  # Limit conversation history
            return v[-100:]  # Keep only last 100 messages
        return v

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "game_id": "game_xyz789",
                "code": "<html>...</html>",
                "metadata": {
                    "title": "My Platformer Game",
                    "game_type": "platformer",
                    "engine": "phaser",
                },
                "current_version": 3,
                "status": "completed",
                "created_at": "2023-12-07T10:00:00Z",
                "updated_at": "2023-12-07T10:30:00Z",
            }
        }


class GameGenerationResult(BaseModel):
    """Result of a game generation operation."""

    success: bool = Field(description="Whether generation was successful")
    game_state: Optional[GameState] = Field(default=None, description="Generated game state")
    session_id: str = Field(description="Session ID")
    generation_time: float = Field(description="Time taken to generate")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Generation warnings")
    tokens_used: Optional[int] = Field(default=None, description="AI tokens consumed")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "session_id": "session_abc123",
                "generation_time": 4.2,
                "warnings": ["Some features may not work on older browsers"],
                "tokens_used": 1250,
            }
        }


class GameTemplate(BaseModel):
    """Game template definition."""

    id: str = Field(description="Template identifier")
    name: str = Field(description="Template name")
    description: str = Field(description="Template description")
    game_type: GameType = Field(description="Game type")
    engine: str = Field(description="Required game engine")
    difficulty: str = Field(description="Difficulty level")
    features: List[str] = Field(description="Included features")
    code_template: str = Field(description="Template code with placeholders")
    placeholders: Dict[str, str] = Field(description="Available placeholders")
    preview_image: Optional[str] = Field(default=None, description="Preview image URL")
    created_at: datetime = Field(description="Template creation date")
    updated_at: datetime = Field(description="Last update date")
    usage_count: int = Field(default=0, description="Number of times used")

    @validator("code_template")
    def validate_template_code(cls, v):
        if len(v) > 512 * 1024:  # 512KB limit for templates
            raise ValueError("Template code too large (max 512KB)")
        return v

    class Config:
        schema_extra = {
            "example": {
                "id": "basic_platformer",
                "name": "Basic Platformer",
                "description": "Simple platformer with jump mechanics",
                "game_type": "platformer",
                "engine": "phaser",
                "difficulty": "beginner",
                "features": ["player_movement", "platforms", "collision"],
                "placeholders": {"PLAYER_COLOR": "blue", "PLATFORM_COLOR": "green"},
                "usage_count": 150,
            }
        }


class CodeValidationResult(BaseModel):
    """Result of code validation."""

    is_valid: bool = Field(description="Whether code passed validation")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    security_issues: List[str] = Field(default_factory=list, description="Security concerns")
    code_metrics: Dict[str, Any] = Field(default_factory=dict, description="Code quality metrics")

    class Config:
        schema_extra = {
            "example": {
                "is_valid": True,
                "errors": [],
                "warnings": ["Large inline script detected"],
                "security_issues": [],
                "code_metrics": {"size_bytes": 15420, "script_tags": 3, "external_resources": 2},
            }
        }


class GameAnalytics(BaseModel):
    """Game analytics and metrics."""

    game_id: str = Field(description="Game identifier")
    session_id: str = Field(description="Session identifier")
    generation_metrics: Dict[str, Any] = Field(description="Generation performance metrics")
    modification_count: int = Field(description="Number of modifications made")
    conversation_length: int = Field(description="Number of messages in conversation")
    feature_complexity: int = Field(description="Complexity score based on features")
    code_quality_score: float = Field(description="Code quality assessment score")
    user_satisfaction: Optional[float] = Field(default=None, description="User satisfaction rating")

    class Config:
        schema_extra = {
            "example": {
                "game_id": "game_xyz789",
                "session_id": "session_abc123",
                "generation_metrics": {
                    "initial_generation_time": 5.2,
                    "avg_modification_time": 2.1,
                    "total_time_spent": 15.6,
                },
                "modification_count": 4,
                "conversation_length": 8,
                "feature_complexity": 7,
                "code_quality_score": 8.5,
            }
        }
