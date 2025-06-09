"""
Game Controller - Enterprise Standard
Handles business logic orchestration for game operations.
Separates business logic from HTTP routing concerns.
"""

import time

# Standard library imports
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
import structlog

# Local application imports
from ..exceptions import BusinessLogicError, ValidationError
from ..models.game_models import GameGenerationRequest, GameGenerationResult
from ..models.response_models import SuccessResponse, create_success_response
from ..services.code_validator import CodeValidator
from ..services.game_generator import GameGenerationError, GameGenerator
from ..services.session_manager import SessionManager
from ..utils.constants import ERROR_MESSAGES

logger = structlog.get_logger(__name__)


class GameController:
    """
    Enterprise-standard controller for game operations.
    Orchestrates business logic without HTTP concerns.
    """

    def __init__(self):
        self.game_generator = GameGenerator()
        self.session_manager = SessionManager()
        self.code_validator = CodeValidator()

    async def create_game(
        self, request: GameGenerationRequest, session_id: Optional[str] = None
    ) -> SuccessResponse:
        """
        Business logic for game creation.

        Args:
            request: Game generation request
            session_id: Optional session identifier

        Returns:
            SuccessResponse with game creation result

        Raises:
            ValidationError: For invalid input
            BusinessLogicError: For generation failures
        """
        try:
            start_time = time.time()

            # Set session_id on request if provided
            if session_id:
                request.session_id = session_id

            logger.info(
                "Creating game",
                prompt=request.prompt[:100],
                game_type=request.game_type,
                session_id=request.session_id,
            )

            # Validate request
            await self._validate_game_request(request)

            # Generate the game
            generation_result = await self.game_generator.generate_game(request)

            # Check if generation was successful
            if not generation_result.success or not generation_result.game_state:
                raise BusinessLogicError(
                    generation_result.error_message or "Game generation failed"
                )

            # Validate generated code
            is_valid, validation_issues = self.game_generator.validate_game_code(
                generation_result.game_state.code
            )

            if not is_valid and validation_issues:
                logger.warning("Generated code has validation issues", issues=validation_issues)

            # Store game in database (would be implemented)
            game_data = self._build_game_response_data(
                generation_result, start_time, is_valid, validation_issues
            )

            return create_success_response(message="Game created successfully", data=game_data)

        except ValidationError:
            raise
        except GameGenerationError as e:
            logger.error("Game generation failed", error=str(e), session_id=session_id)
            raise BusinessLogicError(f"Game generation failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during game creation", error=str(e))
            raise BusinessLogicError(ERROR_MESSAGES["INTERNAL_ERROR"])

    async def get_game_info(self, session_id: str, game_id: str) -> SuccessResponse:
        """
        Business logic for retrieving game information.

        Args:
            session_id: Session identifier
            game_id: Game identifier

        Returns:
            SuccessResponse with game information
        """
        try:
            # Validate session and game access
            await self._validate_game_access(session_id, game_id)

            # Get game information (placeholder for now)
            game_info = await self._get_game_information(session_id, game_id)

            return create_success_response(
                message="Game information retrieved successfully", data=game_info
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to retrieve game info", session_id=session_id, game_id=game_id, error=str(e)
            )
            raise BusinessLogicError("Failed to retrieve game information")

    async def validate_game_code(self, session_id: str, game_id: str) -> SuccessResponse:
        """
        Business logic for game code validation.

        Args:
            session_id: Session identifier
            game_id: Game identifier

        Returns:
            SuccessResponse with validation results
        """
        try:
            # Validate access
            await self._validate_game_access(session_id, game_id)

            # Get game code and validate
            game_code = await self._get_game_code(session_id, game_id)
            validation_result = await self.code_validator.validate_game_code(game_code)

            return create_success_response(
                message="Game validation completed",
                data={
                    "game_id": game_id,
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "security_issues": validation_result.security_issues,
                },
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Game validation failed", session_id=session_id, game_id=game_id, error=str(e)
            )
            raise BusinessLogicError("Game validation failed")

    async def get_session_analytics(self, session_id: str) -> SuccessResponse:
        """
        Business logic for session analytics.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with analytics data
        """
        try:
            # Validate session
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise ValidationError("Invalid session ID")

            # Get metrics
            metrics = await self.session_manager.get_session_metrics(session_id)

            analytics_data = {
                "session_id": session_id,
                "games_created": session.generation_count,
                "modifications_made": session.modifications_made,
                "session_duration": self._calculate_session_duration(session),
                "metrics": metrics.dict() if metrics else None,
            }

            return create_success_response(
                message="Analytics retrieved successfully", data=analytics_data
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error("Failed to get analytics", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to retrieve analytics")

    # Private helper methods for business logic

    async def _validate_game_request(self, request: GameGenerationRequest) -> None:
        """Validate game generation request."""
        if not request.prompt or len(request.prompt.strip()) < 10:
            raise ValidationError("Game prompt must be at least 10 characters")

        if len(request.prompt) > 5000:
            raise ValidationError("Game prompt too long (max 5000 characters)")

    async def _validate_game_access(self, session_id: str, game_id: str) -> None:
        """Validate user has access to the game."""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError("Invalid session ID")

        if game_id not in session.games:
            raise ValidationError("Game not found in session")

    async def _handle_session_management(self, session_id: str, game_state) -> str:
        """Handle session and game state management."""
        await self.session_manager.add_game_to_session(session_id, game_state)
        return session_id

    async def _get_game_information(self, session_id: str, game_id: str) -> Dict[str, Any]:
        """Get comprehensive game information."""
        # Placeholder - would load from storage
        return {
            "game_id": game_id,
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
            "version": 1,
        }

    async def _get_game_code(self, session_id: str, game_id: str) -> str:
        """Retrieve game code for validation."""
        # Placeholder - would load from storage
        return "<html><!-- Game code placeholder --></html>"

    def _build_game_response_data(
        self,
        result: GameGenerationResult,
        start_time: float,
        is_valid: bool,
        validation_issues: List[str],
    ) -> Dict[str, Any]:
        """Build standardized game response data."""
        if not result.game_state:
            return {
                "session_id": result.session_id,
                "success": False,
                "error": result.error_message,
                "generation_time": time.time() - start_time,
            }

        game_state = result.game_state
        return {
            "session_id": result.session_id,
            "game_code": game_state.code,
            "game_id": game_state.game_id,
            "game_type": game_state.metadata.game_type,
            "engine": game_state.metadata.engine,
            "generation_time": time.time() - start_time,
            "tokens_used": result.tokens_used or 0,
            "version": game_state.current_version,
            "warnings": result.warnings or [],
            "is_valid": is_valid,
            "validation_issues": validation_issues,
        }

    def _calculate_session_duration(self, session) -> float:
        """Calculate session duration in seconds."""
        if not session.session_info.created_at:
            return 0.0
        return (datetime.utcnow() - session.session_info.created_at).total_seconds()
