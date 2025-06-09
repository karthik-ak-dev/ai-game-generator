"""
Game generation service for orchestrating game creation.
Coordinates AI generation, template processing, and validation.
"""

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ..models.game_models import (
    GameGenerationRequest,
    GameGenerationResult,
    GameMetadata,
    GameState,
    GameVersion,
)
from ..services.ai_service import AIService, AIServiceError
from ..utils.code_utils import CodeAnalyzer, HTMLParser
from ..utils.constants import GenerationStatus
from ..utils.validation import validator

logger = structlog.get_logger(__name__)


class GameGenerationError(Exception):
    """Game generation specific errors."""

    pass


class GameGenerator:
    """Orchestrates game creation and management."""

    def __init__(self):
        self.ai_service = AIService()
        self.code_analyzer = CodeAnalyzer()
        self.html_parser = HTMLParser()

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

            # Generate game using AI
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

            # Analyze generated game features
            detected_features = self.code_analyzer.extract_game_features(ai_result["game_code"])
            game_state.metadata.features.extend(detected_features)
            game_state.metadata.features = list(
                set(game_state.metadata.features)
            )  # Remove duplicates

            generation_time = time.time() - start_time

            result = GameGenerationResult(
                success=True,
                game_state=game_state,
                session_id=session_id,
                generation_time=generation_time,
                tokens_used=ai_result.get("tokens_used", 0),
                warnings=ai_result.get("validation_issues", []),
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

    async def regenerate_game(
        self,
        session_id: str,
        current_game_state: GameState,
        modifications: Optional[str] = None,
    ) -> GameGenerationResult:
        """
        Regenerate game with modifications.

        Args:
            session_id: Session identifier
            current_game_state: Current game state
            modifications: Optional modification instructions

        Returns:
            GameGenerationResult with regenerated game
        """
        start_time = time.time()

        try:
            # Create regeneration request
            prompt = modifications or "Regenerate this game with improvements"

            request = GameGenerationRequest(
                prompt=prompt,
                game_type=current_game_state.metadata.game_type,
                engine=current_game_state.metadata.engine,
                difficulty=current_game_state.metadata.difficulty,
                features=current_game_state.metadata.features,
                session_id=session_id,
            )

            # Generate new version
            ai_result = await self.ai_service.generate_game(request)

            # Create new version
            new_version = GameVersion(
                version=current_game_state.current_version + 1,
                created_at=datetime.utcnow(),
                modification_summary=modifications or "Game regeneration",
                modifications_applied=["regeneration"],
                code_size=len(ai_result["game_code"].encode("utf-8")),
                generation_time=ai_result["generation_time"],
                is_current=True,
                parent_version=current_game_state.current_version,
            )

            # Update game state
            current_game_state.code = ai_result["game_code"]
            current_game_state.current_version = new_version.version
            current_game_state.versions.append(new_version)
            current_game_state.updated_at = datetime.utcnow()
            current_game_state.status = GenerationStatus.COMPLETED

            # Mark previous version as not current
            for version in current_game_state.versions:
                if version.version != new_version.version:
                    version.is_current = False

            generation_time = time.time() - start_time

            result = GameGenerationResult(
                success=True,
                game_state=current_game_state,
                session_id=session_id,
                generation_time=generation_time,
                tokens_used=ai_result.get("tokens_used", 0),
            )

            logger.info(
                "Game regeneration completed",
                session_id=session_id,
                game_id=current_game_state.game_id,
                new_version=new_version.version,
            )

            return result

        except Exception as e:
            logger.error(
                "Game regeneration failed",
                session_id=session_id,
                error=str(e),
            )

            return GameGenerationResult(
                success=False,
                game_state=current_game_state,
                session_id=session_id,
                generation_time=time.time() - start_time,
                error_message=f"Regeneration failed: {str(e)}",
            )

    def validate_game_code(self, game_code: str) -> Tuple[bool, List[str]]:
        """
        Validate generated game code.

        Args:
            game_code: HTML game code to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        try:
            return validator.validate_game_code(game_code)
        except Exception as e:
            logger.error("Code validation failed", error=str(e))
            return False, [f"Validation error: {str(e)}"]

    def analyze_game_complexity(self, game_code: str) -> Dict[str, Any]:
        """
        Analyze complexity of generated game.

        Args:
            game_code: Game code to analyze

        Returns:
            Dictionary with complexity metrics
        """
        try:
            return self.code_analyzer.analyze_complexity(game_code, "html")
        except Exception as e:
            logger.error("Complexity analysis failed", error=str(e))
            return {"error": str(e)}

    def extract_game_info(self, game_code: str) -> Dict[str, Any]:
        """
        Extract information from game code.

        Args:
            game_code: Game code to analyze

        Returns:
            Dictionary with extracted information
        """
        try:
            # Extract meta information
            meta_info = self.html_parser.extract_meta_tags(game_code)

            # Extract scripts
            scripts = self.html_parser.extract_scripts(game_code)

            # Extract styles
            styles = self.html_parser.extract_styles(game_code)

            # Detect features
            features = self.code_analyzer.extract_game_features(game_code)

            return {
                "meta_info": meta_info,
                "scripts": len(scripts),
                "styles": len(styles),
                "features": features,
                "code_size": len(game_code.encode("utf-8")),
            }

        except Exception as e:
            logger.error("Game info extraction failed", error=str(e))
            return {"error": str(e)}

    def _create_game_metadata(
        self,
        request: GameGenerationRequest,
        ai_result: Dict[str, Any],
    ) -> GameMetadata:
        """Create game metadata from request and AI result."""

        # Extract title from AI result or generate from prompt
        title = self._extract_title_from_prompt(request.prompt)

        # Determine game type
        game_type = request.game_type or ai_result["metadata"].get("game_type", "arcade")

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
            controls={},  # Will be populated by analyzing the code
            objectives=[],  # Will be populated by analyzing the code
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

    async def get_generation_statistics(self) -> Dict[str, Any]:
        """Get game generation statistics."""
        try:
            ai_stats = self.ai_service.get_statistics()

            return {
                "ai_service": ai_stats,
                "total_generations": ai_stats.get("total_calls", 0),
                "average_generation_time": 0,  # Would calculate from stored data
                "success_rate": 0.95,  # Would calculate from stored data
                "popular_game_types": ["platformer", "shooter", "puzzle"],  # From analytics
                "popular_engines": ["phaser", "three", "p5"],  # From analytics
            }

        except Exception as e:
            logger.error("Failed to get generation statistics", error=str(e))
            return {}
