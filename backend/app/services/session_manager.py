"""
Session manager for core AI game generation functionality.
Manages session lifecycle, game state persistence - Redis-only, stateless design.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog

from ..config import settings
from ..models.game_models import GameState
from ..models.session_models import SessionCreationRequest, SessionInfo, SessionState
from ..utils.constants import SessionStatus
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class SessionError(Exception):
    """Session management specific errors."""

    pass


class SessionManager:
    """Stateless session manager for core game generation workflow."""

    def __init__(self):
        # No local state - completely stateless for container scaling
        pass

    async def create_session(
        self, request: Optional[SessionCreationRequest] = None
    ) -> SessionState:
        """
        Create a new game development session.

        Args:
            request: Optional session creation request

        Returns:
            SessionState object
        """
        try:
            session_id = self._generate_session_id()
            current_time = datetime.utcnow()
            expires_at = current_time + timedelta(seconds=settings.session.ttl)

            # Create session info
            session_info = SessionInfo(
                session_id=session_id,
                status=SessionStatus.ACTIVE,
                created_at=current_time,
                last_activity=current_time,
                expires_at=expires_at,
                user_id=request.user_id if request else None,
                ip_address=(
                    request.client_info.get("ip_address")
                    if request and request.client_info
                    else None
                ),
                user_agent=(
                    request.client_info.get("user_agent")
                    if request and request.client_info
                    else None
                ),
            )

            # Create session state with proper defaults
            session_state = SessionState(
                session_info=session_info,
                preferences=request.preferences if request and request.preferences else {},
                metadata={
                    "created_by": "api",
                    "initial_prompt": request.initial_prompt if request else None,
                },
            )

            # Store session directly in Redis
            success = await self._store_session(session_state)
            if not success:
                raise SessionError("Failed to store session in Redis")

            logger.info("Session created", session_id=session_id, user_id=session_info.user_id)

            return session_state

        except Exception as e:
            logger.error("Failed to create session", error=str(e))
            raise SessionError(f"Session creation failed: {str(e)}")

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get session by ID from Redis with automatic extension.

        Args:
            session_id: Session identifier

        Returns:
            SessionState object or None if not found or expired
        """
        try:
            # Load directly from Redis
            session_data = await redis_service.get_session(session_id)
            if not session_data:
                return None

            try:
                session = SessionState.parse_obj(session_data)

                # Check if session is expired
                if session.session_info.expires_at < datetime.utcnow():
                    await self._expire_session(session_id)
                    return None

                # Auto-extend session on access and update last activity
                session.session_info.last_activity = datetime.utcnow()
                session.session_info.expires_at = datetime.utcnow() + timedelta(
                    seconds=settings.session.ttl
                )
                await self._store_session(session)

                return session

            except Exception as e:
                logger.error("Failed to parse session data", session_id=session_id, error=str(e))
                # Clean up corrupted session data
                await redis_service.delete_session(session_id)
                return None

        except Exception as e:
            logger.error("Failed to get session", session_id=session_id, error=str(e))
            return None

    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session and clean up resources.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Remove from Redis
            success = await redis_service.delete_session(session_id)

            if success:
                logger.info("Session terminated", session_id=session_id)

            return success

        except Exception as e:
            logger.error("Failed to terminate session", session_id=session_id, error=str(e))
            return False

    async def add_game_to_session(self, session_id: str, game_state: GameState) -> bool:
        """
        Add a generated game to a session.

        Args:
            session_id: Session identifier
            game_state: Game state to add

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Add game to session
            session.games.append(game_state.game_id)
            session.current_game_id = game_state.game_id
            session.generation_count += 1
            session.session_info.last_activity = datetime.utcnow()

            # Store updated session
            success = await self._store_session(session)

            if success:
                logger.info(
                    "Game added to session", session_id=session_id, game_id=game_state.game_id
                )

            return success

        except Exception as e:
            logger.error("Failed to add game to session", session_id=session_id, error=str(e))
            return False

    async def increment_message_count(self, session_id: str) -> bool:
        """
        Increment conversation message count for session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            session.conversation_messages += 1
            session.session_info.last_activity = datetime.utcnow()

            return await self._store_session(session)

        except Exception as e:
            logger.error("Failed to increment message count", session_id=session_id, error=str(e))
            return False

    async def increment_modification_count(self, session_id: str) -> bool:
        """
        Increment game modification count for session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            session.modifications_made += 1
            session.session_info.last_activity = datetime.utcnow()

            return await self._store_session(session)

        except Exception as e:
            logger.error(
                "Failed to increment modification count", session_id=session_id, error=str(e)
            )
            return False

    # Private Methods

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"session_{uuid.uuid4().hex[:12]}"

    async def _store_session(self, session_state: SessionState) -> bool:
        """Store session state in Redis only."""
        try:
            session_data = session_state.dict()
            success = await redis_service.store_session(
                session_state.session_info.session_id, session_data, settings.session.ttl
            )
            return success
        except Exception as e:
            logger.error(
                "Failed to store session",
                session_id=session_state.session_info.session_id,
                error=str(e),
            )
            return False

    async def _expire_session(self, session_id: str) -> None:
        """Expire a session by removing it from Redis."""
        try:
            # Remove from Redis
            await redis_service.delete_session(session_id)
            logger.info("Session expired", session_id=session_id)

        except Exception as e:
            logger.error("Failed to expire session", session_id=session_id, error=str(e))
