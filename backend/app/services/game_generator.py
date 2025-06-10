"""
Game generation service for orchestrating game creation.
Production-ready orchestrator focused on core functionality.
"""

import time
import uuid
from datetime import datetime
from typing import Any, Dict

import structlog

from ..models.game_models import (
    GameGenerationRequest,
    GameGenerationResult,
    GameMetadata,
    GameState,
    GameVersion,
)
from ..services.ai_service import AIService, AIServiceError
from ..utils.constants import GameType, GenerationStatus

logger = structlog.get_logger(__name__)


class GameGenerationError(Exception):
    """Game generation specific errors."""

    pass


class GameGenerator:
    """Production game generator orchestrating AI service for game creation."""

    def __init__(self):
        self.ai_service = AIService()

    async def generate_game(self, request: GameGenerationRequest) -> GameGenerationResult:
        """
        Generate a complete game from user request.

        Args:
            request: Game generation request

        Returns:
            GameGenerationResult with generated game
        """
        start_time = time.time()
        session_id = request.session_id or self._generate_session_id()

        try:
            logger.info(
                "Starting game generation",
                session_id=session_id,
                game_type=request.game_type,
                engine=request.engine,
            )

            # Generate game using AI service
            ai_result = await self.ai_service.generate_game(request)

            # Create game metadata
            metadata = self._create_game_metadata(request, ai_result)

            # Create initial game version
            initial_version = GameVersion(
                version=1,
                created_at=datetime.utcnow(),
                modification_summary="Initial game creation",
                modifications_applied=["initial_generation"],
                code_size=len(ai_result["game_code"].encode("utf-8")),
                generation_time=ai_result["generation_time"],
                is_current=True,
            )

            # Create game state
            game_id = self._generate_game_id()
            game_state = GameState(
                session_id=session_id,
                game_id=game_id,
                code=ai_result["game_code"],
                metadata=metadata,
                current_version=1,
                versions=[initial_version],
                status=GenerationStatus.COMPLETED,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                conversation_context=[],
            )

            generation_time = time.time() - start_time

            result = GameGenerationResult(
                success=True,
                game_state=game_state,
                session_id=session_id,
                generation_time=generation_time,
                tokens_used=ai_result.get("tokens_used", 0),
                warnings=ai_result.get("warnings", []),
            )

            logger.info(
                "Game generation completed",
                session_id=session_id,
                game_id=game_id,
                generation_time=generation_time,
                code_size=len(ai_result["game_code"]),
            )

            return result

        except AIServiceError as e:
            logger.error(
                "AI service error during generation",
                session_id=session_id,
                error=str(e),
            )

            return GameGenerationResult(
                success=False,
                game_state=None,
                session_id=session_id,
                generation_time=time.time() - start_time,
                error_message=f"AI generation failed: {str(e)}",
            )

        except Exception as e:
            logger.error(
                "Game generation failed",
                session_id=session_id,
                error=str(e),
            )

            return GameGenerationResult(
                success=False,
                game_state=None,
                session_id=session_id,
                generation_time=time.time() - start_time,
                error_message=f"Generation failed: {str(e)}",
            )

    # Private helper methods

    def _create_game_metadata(
        self,
        request: GameGenerationRequest,
        ai_result: Dict[str, Any],
    ) -> GameMetadata:
        """Create game metadata from request and AI result."""

        # Extract title from prompt or use default
        title = self._extract_title_from_prompt(request.prompt)

        # Determine game type and convert to enum
        game_type_str = request.game_type or ai_result["metadata"].get("game_type", "arcade")

        # Convert string to GameType enum
        try:
            game_type = GameType(game_type_str.upper())
        except (ValueError, AttributeError):
            game_type = GameType.ARCADE  # Default fallback

        # Build metadata
        metadata = GameMetadata(
            title=title,
            description=(
                request.prompt[:200] + "..." if len(request.prompt) > 200 else request.prompt
            ),
            game_type=game_type,
            engine=request.engine or "phaser",
            difficulty=request.difficulty or "beginner",
            features=request.features or [],
            controls={},  # Basic controls info
            objectives=["Play and have fun!"],  # Basic objective
            tags=[game_type, request.engine or "phaser"],
        )

        return metadata

    def _extract_title_from_prompt(self, prompt: str) -> str:
        """Extract a game title from the prompt."""
        # Simple title extraction logic
        words = prompt.split()[:5]  # Take first 5 words
        title = " ".join(words).title()

        # Clean up the title
        if len(title) > 50:
            title = title[:47] + "..."

        return title or "My Game"

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"session_{uuid.uuid4().hex[:12]}"

    def _generate_game_id(self) -> str:
        """Generate a unique game ID."""
        return f"game_{uuid.uuid4().hex[:8]}"
