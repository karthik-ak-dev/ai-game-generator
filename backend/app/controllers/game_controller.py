"""
Game Controller for Core AI Game Generation Functionality
Handles essential game operations needed for core workflow.
"""

import time

# Standard library imports
from datetime import datetime
from typing import Any, Dict, Optional

# Third-party imports
import structlog

# Local application imports
from ..exceptions import BusinessLogicError, ValidationError
from ..models.game_models import GameGenerationRequest, GameGenerationResult
from ..models.response_models import SuccessResponse, create_success_response
from ..services.game_generator import GameGenerationError, GameGenerator
from ..services.session_manager import SessionManager
from ..utils.constants import ERROR_MESSAGES

logger = structlog.get_logger(__name__)


class GameController:
    """
    Core controller for game operations.
    Handles essential game generation and retrieval only.
    """

    def __init__(self):
        self.game_generator = GameGenerator()
        self.session_manager = SessionManager()

    async def create_game(
        self, request: GameGenerationRequest, session_id: Optional[str] = None
    ) -> SuccessResponse:
        """
        Generate a new game from user request.

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

            # Build response data
            game_data = self._build_game_response_data(generation_result, start_time)

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
        Retrieve game information.

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
            game_info = {
                "game_id": game_id,
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active",
                "version": 1,
            }

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

    # Private helper methods

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

    def _build_game_response_data(
        self, result: GameGenerationResult, start_time: float
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
        }
