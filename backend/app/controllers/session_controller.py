"""
Session Controller - Enterprise Standard
Handles business logic orchestration for session management operations.
Separates session business logic from HTTP routing concerns.
"""

# Standard library imports
from datetime import datetime
from typing import Any, Dict, Optional

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
    Enterprise-standard controller for session operations.
    Orchestrates session management business logic.
    """

    def __init__(self):
        self.session_manager = SessionManager()

    async def create_session(
        self, request: Optional[SessionCreationRequest] = None
    ) -> SuccessResponse:
        """
        Business logic for session creation.

        Args:
            request: Optional session creation request

        Returns:
            SuccessResponse with new session information

        Raises:
            ValidationError: For invalid input
            BusinessLogicError: For creation failures
        """
        try:
            logger.info("Creating new session")

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
        Business logic for retrieving session information.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with session information
        """
        try:
            # Get session
            session = await self._get_valid_session(session_id)

            # Build session info response
            session_data = {
                "session_id": session.session_info.session_id,
                "status": session.session_info.status.value,
                "created_at": session.session_info.created_at.isoformat(),
                "last_activity": session.session_info.last_activity.isoformat(),
                "expires_at": session.session_info.expires_at.isoformat(),
                "user_id": session.session_info.user_id,
                "games": session.games,
                "current_game_id": session.current_game_id,
                "generation_count": session.generation_count,
                "modifications_made": session.modifications_made,
                "message_count": session.conversation_messages,
            }

            return create_success_response(
                message="Session information retrieved", data=session_data
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to get session info", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to retrieve session information")

    async def update_session_preferences(
        self, session_id: str, preferences: Dict[str, Any]
    ) -> SuccessResponse:
        """
        Business logic for updating session preferences.

        Args:
            session_id: Session identifier
            preferences: New preferences

        Returns:
            SuccessResponse with updated preferences
        """
        try:
            # Validate session
            await self._get_valid_session(session_id)

            # Validate preferences
            await self._validate_preferences(preferences)

            # Update preferences using the update_session method
            success = await self.session_manager.update_session(
                session_id, {"preferences": preferences}
            )

            if not success:
                raise BusinessLogicError("Failed to update session preferences")

            return create_success_response(
                message="Session preferences updated",
                data={"session_id": session_id, "preferences": preferences},
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Failed to update session preferences", session_id=session_id, error=str(e)
            )
            raise BusinessLogicError("Failed to update preferences")

    async def get_session_metrics(self, session_id: str) -> SuccessResponse:
        """
        Business logic for retrieving session metrics.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with session metrics
        """
        try:
            # Validate session
            session = await self._get_valid_session(session_id)

            # Get metrics
            metrics = await self.session_manager.get_session_metrics(session_id)

            # Build metrics response
            metrics_data = {
                "session_id": session_id,
                "session_duration": self._calculate_session_duration(session),
                "activity_count": {
                    "games_generated": session.generation_count,
                    "modifications_made": session.modifications_made,
                    "messages_sent": session.conversation_messages,
                },
                "performance_metrics": metrics.dict() if metrics else None,
                "last_activity": session.session_info.last_activity.isoformat(),
            }

            return create_success_response(message="Session metrics retrieved", data=metrics_data)

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to get session metrics", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to retrieve session metrics")

    async def extend_session(self, session_id: str) -> SuccessResponse:
        """
        Business logic for extending session expiration.

        Args:
            session_id: Session identifier

        Returns:
            SuccessResponse with extended session info
        """
        try:
            # Get and validate session exists
            await self._get_valid_session(session_id)

            # Extend session
            success = await self.session_manager.extend_session(session_id)

            if not success:
                raise BusinessLogicError("Failed to extend session")

            # Get updated session info
            updated_session = await self.session_manager.get_session(session_id)

            response_data = {
                "session_id": session_id,
                "extended": True,
                "new_expires_at": (
                    updated_session.session_info.expires_at.isoformat() if updated_session else None
                ),
            }

            return create_success_response(
                message="Session extended successfully", data=response_data
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error("Failed to extend session", session_id=session_id, error=str(e))
            raise BusinessLogicError("Failed to extend session")

    async def cleanup_session(self, session_id: str) -> SuccessResponse:
        """
        Business logic for session cleanup.

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

    async def get_active_sessions_summary(self) -> SuccessResponse:
        """
        Business logic for getting active sessions summary.

        Returns:
            SuccessResponse with active sessions summary
        """
        try:
            # Get active sessions count using correct method name
            active_count = await self.session_manager.get_active_session_count()

            summary_data = {
                "active_sessions": active_count,
                "timestamp": datetime.utcnow().isoformat(),
                "system_status": "operational",
            }

            return create_success_response(
                message="Active sessions summary retrieved", data=summary_data
            )

        except Exception as e:
            logger.error("Failed to get active sessions summary", error=str(e))
            raise BusinessLogicError("Failed to retrieve sessions summary")

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

    async def _validate_preferences(self, preferences: Dict[str, Any]) -> None:
        """Validate session preferences."""
        allowed_keys = {
            "theme",
            "language",
            "auto_save",
            "notifications",
            "code_style",
            "ai_assistance_level",
        }

        for key in preferences.keys():
            if key not in allowed_keys:
                raise ValidationError(f"Invalid preference key: {key}")

        # Validate specific preference values
        if "theme" in preferences and preferences["theme"] not in ["light", "dark", "auto"]:
            raise ValidationError("Theme must be 'light', 'dark', or 'auto'")

        if "language" in preferences and not isinstance(preferences["language"], str):
            raise ValidationError("Language must be a string")

    def _calculate_session_duration(self, session) -> float:
        """Calculate session duration in seconds."""
        if not session.session_info.created_at:
            return 0.0
        return (datetime.utcnow() - session.session_info.created_at).total_seconds()
