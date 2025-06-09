"""
Template management data models for AI Game Generator.
Defines structures for game templates, template metadata, and template operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from ..utils.constants import GAME_ENGINES, GameType


class TemplateMetadata(BaseModel):
    """Template metadata and configuration."""

    name: str = Field(description="Template display name")
    description: str = Field(description="Template description")
    game_type: GameType = Field(description="Type of game this template creates")
    engine: str = Field(description="Required game engine")
    difficulty: str = Field(description="Target difficulty level")
    version: str = Field(default="1.0.0", description="Template version")
    author: Optional[str] = Field(default=None, description="Template author")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    features: List[str] = Field(description="Features included in this template")
    requirements: List[str] = Field(default_factory=list, description="Technical requirements")

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

    class Config:
        schema_extra = {
            "example": {
                "name": "Basic Platformer",
                "description": "A simple platformer with jump mechanics and collectibles",
                "game_type": "platformer",
                "engine": "phaser",
                "difficulty": "beginner",
                "version": "1.0.0",
                "author": "AI Game Generator",
                "tags": ["2d", "platformer", "beginner-friendly"],
                "features": ["player_movement", "jumping", "platforms", "collision"],
                "requirements": ["modern_browser", "javascript_enabled"],
            }
        }


class TemplateVariable(BaseModel):
    """Template variable definition."""

    name: str = Field(description="Variable name")
    type: str = Field(description="Variable type (string, number, boolean, color)")
    default_value: Any = Field(description="Default value")
    description: str = Field(description="Variable description")
    required: bool = Field(default=False, description="Whether variable is required")
    options: Optional[List[Any]] = Field(default=None, description="Valid options for the variable")
    min_value: Optional[float] = Field(default=None, description="Minimum value (for numbers)")
    max_value: Optional[float] = Field(default=None, description="Maximum value (for numbers)")

    @validator("type")
    def validate_type(cls, v):
        valid_types = {"string", "number", "boolean", "color", "array", "object"}
        if v not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "player_color",
                "type": "color",
                "default_value": "#0066cc",
                "description": "Color of the player character",
                "required": False,
                "options": ["#0066cc", "#cc0000", "#00cc00", "#cc6600"],
            }
        }


class GameTemplate(BaseModel):
    """Complete game template definition."""

    id: str = Field(description="Unique template identifier")
    metadata: TemplateMetadata = Field(description="Template metadata")
    code_template: str = Field(description="Template code with placeholders")
    variables: List[TemplateVariable] = Field(description="Template variables")
    preview_code: Optional[str] = Field(default=None, description="Preview code for template")
    preview_image: Optional[str] = Field(default=None, description="Preview image URL")
    instructions: Optional[str] = Field(default=None, description="Usage instructions")
    created_at: datetime = Field(description="Template creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    usage_count: int = Field(default=0, description="Number of times used")
    rating: Optional[float] = Field(default=None, description="Average user rating")
    is_active: bool = Field(default=True, description="Whether template is active")

    @validator("code_template")
    def validate_code_template(cls, v):
        if len(v) > 1024 * 1024:  # 1MB limit
            raise ValueError("Template code too large (max 1MB)")
        if not v.strip():
            raise ValueError("Template code cannot be empty")
        return v

    @validator("rating")
    def validate_rating(cls, v):
        if v is not None and (v < 0 or v > 5):
            raise ValueError("Rating must be between 0 and 5")
        return v

    class Config:
        schema_extra = {
            "example": {
                "id": "basic_platformer_v1",
                "metadata": {
                    "name": "Basic Platformer",
                    "description": "Simple platformer template",
                    "game_type": "platformer",
                    "engine": "phaser",
                },
                "code_template": "<!DOCTYPE html>...",
                "variables": [],
                "usage_count": 150,
                "rating": 4.5,
                "is_active": True,
            }
        }


class TemplateCreationRequest(BaseModel):
    """Request model for creating a new template."""

    metadata: TemplateMetadata = Field(description="Template metadata")
    code_template: str = Field(description="Template code")
    variables: List[TemplateVariable] = Field(description="Template variables")
    preview_code: Optional[str] = Field(default=None, description="Preview code")
    instructions: Optional[str] = Field(default=None, description="Usage instructions")

    class Config:
        schema_extra = {
            "example": {
                "metadata": {
                    "name": "My Custom Template",
                    "description": "A custom game template",
                    "game_type": "shooter",
                    "engine": "phaser",
                },
                "code_template": "<!DOCTYPE html>...",
                "variables": [],
            }
        }


class TemplateUpdateRequest(BaseModel):
    """Request model for updating an existing template."""

    metadata: Optional[TemplateMetadata] = Field(default=None, description="Updated metadata")
    code_template: Optional[str] = Field(default=None, description="Updated template code")
    variables: Optional[List[TemplateVariable]] = Field(
        default=None, description="Updated variables"
    )
    preview_code: Optional[str] = Field(default=None, description="Updated preview code")
    instructions: Optional[str] = Field(default=None, description="Updated instructions")
    is_active: Optional[bool] = Field(default=None, description="Updated active status")


class TemplateInstantiation(BaseModel):
    """Request for instantiating a template with specific values."""

    template_id: str = Field(description="Template identifier")
    variable_values: Dict[str, Any] = Field(description="Values for template variables")
    additional_prompt: Optional[str] = Field(
        default=None, description="Additional customization prompt"
    )

    class Config:
        schema_extra = {
            "example": {
                "template_id": "basic_platformer_v1",
                "variable_values": {
                    "player_color": "#ff0000",
                    "platform_color": "#00ff00",
                    "game_title": "My Platform Adventure",
                },
                "additional_prompt": "Add power-ups that make the player jump higher",
            }
        }


class TemplateValidationResult(BaseModel):
    """Result of template validation."""

    is_valid: bool = Field(description="Whether template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    missing_variables: List[str] = Field(
        default_factory=list, description="Missing required variables"
    )
    unused_variables: List[str] = Field(
        default_factory=list, description="Defined but unused variables"
    )
    code_metrics: Dict[str, Any] = Field(default_factory=dict, description="Code quality metrics")

    class Config:
        schema_extra = {
            "example": {
                "is_valid": True,
                "errors": [],
                "warnings": ["Large template size"],
                "missing_variables": [],
                "unused_variables": ["deprecated_var"],
                "code_metrics": {"size_bytes": 25600, "complexity_score": 7},
            }
        }


class TemplateSearchRequest(BaseModel):
    """Request model for searching templates."""

    query: Optional[str] = Field(default=None, description="Search query")
    game_type: Optional[GameType] = Field(default=None, description="Filter by game type")
    engine: Optional[str] = Field(default=None, description="Filter by engine")
    difficulty: Optional[str] = Field(default=None, description="Filter by difficulty")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    min_rating: Optional[float] = Field(default=None, description="Minimum rating")
    sort_by: Optional[str] = Field(default="popularity", description="Sort criteria")
    sort_order: Optional[str] = Field(default="desc", description="Sort order")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size")

    @validator("sort_by")
    def validate_sort_by(cls, v):
        valid_sorts = {"popularity", "rating", "created_at", "updated_at", "name", "usage_count"}
        if v not in valid_sorts:
            raise ValueError(f"Sort by must be one of {valid_sorts}")
        return v

    @validator("sort_order")
    def validate_sort_order(cls, v):
        if v not in {"asc", "desc"}:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v


class TemplateSearchResult(BaseModel):
    """Search result for templates."""

    templates: List[GameTemplate] = Field(description="Found templates")
    total_count: int = Field(description="Total number of matching templates")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Page size")
    has_more: bool = Field(description="Whether there are more results")


class TemplateUsageStats(BaseModel):
    """Usage statistics for a template."""

    template_id: str = Field(description="Template identifier")
    total_uses: int = Field(description="Total number of uses")
    unique_users: int = Field(description="Number of unique users")
    successful_generations: int = Field(description="Successful generations")
    failed_generations: int = Field(description="Failed generations")
    average_rating: Optional[float] = Field(default=None, description="Average user rating")
    rating_count: int = Field(default=0, description="Number of ratings")
    popular_modifications: List[str] = Field(description="Most common modifications made")
    usage_by_month: Dict[str, int] = Field(description="Usage statistics by month")

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.successful_generations + self.failed_generations
        if total == 0:
            return 0.0
        return self.successful_generations / total

    class Config:
        schema_extra = {
            "example": {
                "template_id": "basic_platformer_v1",
                "total_uses": 1250,
                "unique_users": 890,
                "successful_generations": 1200,
                "failed_generations": 50,
                "average_rating": 4.3,
                "rating_count": 156,
                "popular_modifications": ["character_color", "add_enemies", "sound_effects"],
                "usage_by_month": {"2023-11": 450, "2023-12": 800},
            }
        }


class TemplateRating(BaseModel):
    """User rating for a template."""

    template_id: str = Field(description="Template identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    session_id: str = Field(description="Session identifier")
    rating: int = Field(ge=1, le=5, description="Rating score (1-5)")
    comment: Optional[str] = Field(default=None, description="Rating comment")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Rating timestamp")

    @validator("comment")
    def validate_comment(cls, v):
        if v and len(v) > 1000:
            raise ValueError("Comment too long (max 1000 characters)")
        return v

    class Config:
        schema_extra = {
            "example": {
                "template_id": "basic_platformer_v1",
                "session_id": "session_abc123",
                "rating": 5,
                "comment": "Great template! Easy to customize and works perfectly.",
                "timestamp": "2023-12-07T10:30:00Z",
            }
        }


class TemplateCategory(BaseModel):
    """Template category definition."""

    id: str = Field(description="Category identifier")
    name: str = Field(description="Category name")
    description: str = Field(description="Category description")
    parent_id: Optional[str] = Field(default=None, description="Parent category ID")
    template_count: int = Field(default=0, description="Number of templates in category")
    is_active: bool = Field(default=True, description="Whether category is active")

    class Config:
        schema_extra = {
            "example": {
                "id": "2d_games",
                "name": "2D Games",
                "description": "Templates for 2D game development",
                "parent_id": None,
                "template_count": 25,
                "is_active": True,
            }
        }
