"""
Session Controller - Core Functionality
Handles essential session management operations for AI game generation workflow.
"""

# Standard library imports
from datetime import datetime
from typing import Optional

# Third-party imports
import structlog

# Local application imports
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError
from ..models.response_models import SuccessResponse, create_success_response
from ..models.session_models import SessionCreationRequest
from ..services.session_manager import SessionError, SessionManager
from ..utils.constants import ERROR_MESSAGES, SUCCESS_MESSAGES

logger = structlog.get_logger(__name__)


class SessionController:
    """
    Core session controller for AI game generation workflow.
    Handles essential session operations only.
    """

    def __init__(self):
        self.session_manager = SessionManager()

    async def create_session(
        self, request: Optional[SessionCreationRequest] = None
    ) -> SuccessResponse:
        """
        Create a new game development session.

        Args:
            request: Optional session creation request

        Returns:
            SuccessResponse with new session information

        Raises:
            ValidationError: For invalid input
            BusinessLogicError: For creation failures
        """
        try:
            logger.info("Creating new game development session")

            # Validate request if provided
            if request:
                await self._validate_session_request(request)

            # Create session
            session_state = await self.session_manager.create_session(request)

            # Build response data
            response_data = {
                "session_id": session_state.session_info.session_id,
                "status": session_state.session_info.status.value,
                "created_at": session_state.session_info.created_at.isoformat(),
                "expires_at": session_state.session_info.expires_at.isoformat(),
                "preferences": session_state.preferences,
                "metadata": session_state.metadata,
            }

            return create_success_response(
                message=SUCCESS_MESSAGES["SESSION_CREATED"], data=response_data
            )

        except ValidationError:
            raise
        except SessionError as e:
            logger.error("Session creation failed", error=str(e))
            raise BusinessLogicError(f"Session creation failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in session creation", error=str(e))
            raise BusinessLogicError(ERROR_MESSAGES["INTERNAL_ERROR"])

    async def get_session_info(self, session_id: str) -> SuccessResponse:
        """
        Get current session state including conversation and game information.

        This is the primary method for retrieving all context needed to
        continue a game development conversation.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with comprehensive session information
        """
        try:
            # Get session
            session = await self._get_valid_session(session_id)

            # Build comprehensive session data
            session_data = {
                "session_id": session.session_info.session_id,
                "status": session.session_info.status.value,
                "created_at": session.session_info.created_at.isoformat(),
                "last_activity": session.session_info.last_activity.isoformat(),
                "expires_at": session.session_info.expires_at.isoformat(),
                "user_id": session.session_info.user_id,
                "current_game": {
                    "game_id": session.current_game_id,
                    "games": session.games,
                    "generation_count": session.generation_count,
                    "modifications_made": session.modifications_made,
                },
                "conversation": {
                    "message_count": session.conversation_messages,
                    # Add conversation history if needed
                },
                "session_stats": {
                    "duration": self._calculate_session_duration(session),
                    "activity_level": "active" if session.modifications_made > 0 else "new",
                },
            }

            return create_success_response(
                message="Session state retrieved successfully", data=session_data
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to get session info", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to retrieve session information")

    async def cleanup_session(self, session_id: str) -> SuccessResponse:
        """
        Clean up session and release all associated resources.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with cleanup confirmation
        """
        try:
            # Validate session exists
            await self._get_valid_session(session_id)

            # Cleanup session using terminate_session
            success = await self.session_manager.terminate_session(session_id)

            if not success:
                raise BusinessLogicError("Failed to cleanup session")

            return create_success_response(
                message="Session cleaned up successfully",
                data={"session_id": session_id, "cleaned_up": True},
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to cleanup session", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to cleanup session")

    # Private helper methods

    async def _validate_session_request(self, request: SessionCreationRequest) -> None:
        """Validate session creation request."""
        if request.user_id and len(request.user_id) > 100:
            raise ValidationError("User ID too long (max 100 characters)")

        if request.initial_prompt and len(request.initial_prompt) > 1000:
            raise ValidationError("Initial prompt too long (max 1000 characters)")

    async def _get_valid_session(self, session_id: str):
        """Get and validate session exists."""
        if not session_id:
            raise ValidationError("Session ID is required")

        session = await self.session_manager.get_session(session_id)
        if not session:
            raise NotFoundError("Session", session_id)

        return session

    def _calculate_session_duration(self, session) -> float:
        """Calculate session duration in seconds."""
        if not session.session_info.created_at:
            return 0.0
        return (datetime.utcnow() - session.session_info.created_at).total_seconds()
