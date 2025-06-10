"""
Game-related data models for AI Game Generator.
Defines structures for game creation and state management.
"""

# Standard library imports
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
from pydantic import BaseModel, Field, validator

from ..utils.constants import GAME_ENGINES, GameType, GenerationStatus


class GameGenerationRequest(BaseModel):
    """Request model for game generation."""

    prompt: str = Field(..., description="Description of the game to generate")
    game_type: Optional[str] = Field(default="arcade", description="Type of game")
    engine: Optional[str] = Field(default="phaser", description="Game engine to use")
    difficulty: Optional[str] = Field(default="beginner", description="Game difficulty level")
    features: Optional[List[str]] = Field(default=[], description="Specific features to include")
    session_id: Optional[str] = Field(default=None, description="Session identifier")

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
