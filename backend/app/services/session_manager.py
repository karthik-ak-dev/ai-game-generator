"""
Session manager for handling user sessions and state management.
Manages session lifecycle, game state persistence, and cleanup - Redis-only, stateless design.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from ..config import settings
from ..models.game_models import GameState
from ..models.session_models import (
    SessionCreationRequest,
    SessionInfo,
    SessionMetrics,
    SessionState,
    SessionSummary,
)
from ..utils.constants import REDIS_KEYS, SessionStatus
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class SessionError(Exception):
    """Session management specific errors."""

    pass


class SessionManager:
    """Stateless session manager that depends entirely on Redis for persistence."""

    def __init__(self):
        # No local state - completely stateless for container scaling
        pass

    async def create_session(
        self, request: Optional[SessionCreationRequest] = None
    ) -> SessionState:
        """
        Create a new session.

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

            # Log activity
            await self._log_activity(
                session_id,
                "session_created",
                {"user_id": session_info.user_id, "ip_address": session_info.ip_address},
            )

            logger.info("Session created", session_id=session_id, user_id=session_info.user_id)

            return session_state

        except Exception as e:
            logger.error("Failed to create session", error=str(e))
            raise SessionError(f"Session creation failed: {str(e)}")

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get session by ID from Redis.

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

                # Update last activity and store back
                session.session_info.last_activity = datetime.utcnow()
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

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session with new data.

        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Apply updates
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
                elif hasattr(session.session_info, key):
                    setattr(session.session_info, key, value)
                else:
                    session.metadata[key] = value

            # Update timestamp
            session.session_info.last_activity = datetime.utcnow()

            # Store updated session
            success = await self._store_session(session)
            if success:
                logger.info("Session updated", session_id=session_id, updates=list(updates.keys()))

            return success

        except Exception as e:
            logger.error("Failed to update session", session_id=session_id, error=str(e))
            return False

    async def extend_session(
        self, session_id: str, additional_seconds: Optional[int] = None
    ) -> bool:
        """
        Extend session expiration time.

        Args:
            session_id: Session identifier
            additional_seconds: Additional seconds to extend (defaults to session TTL)

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            extension = additional_seconds or settings.session.ttl
            session.session_info.expires_at += timedelta(seconds=extension)
            session.session_info.last_activity = datetime.utcnow()

            # Store updated session and extend Redis TTL
            success = await self._store_session(session)
            if success:
                # Also extend the Redis key TTL
                await redis_service.extend_session(session_id, extension)
                logger.info("Session extended", session_id=session_id, extension_seconds=extension)

            return success

        except Exception as e:
            logger.error("Failed to extend session", session_id=session_id, error=str(e))
            return False

    async def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return False

            # Log activity before termination
            await self._log_activity(session_id, "session_terminated", {"reason": "manual"})

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
        Add a game to a session.

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
                # Log activity
                await self._log_activity(
                    session_id,
                    "game_generated",
                    {"game_id": game_state.game_id, "game_type": game_state.metadata.game_type},
                )

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
        Increment modification count for session.

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

    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """
        Get metrics for a session.

        Args:
            session_id: Session identifier

        Returns:
            SessionMetrics object or None
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return None

            # Calculate duration
            duration = (datetime.utcnow() - session.session_info.created_at).total_seconds()

            # Get activities from Redis
            activities = await self._get_session_activities(session_id)

            # Calculate metrics
            total_requests = len(activities)
            successful_requests = len([a for a in activities if a.get("success", True)])
            failed_requests = total_requests - successful_requests

            # Calculate average response time
            response_times = [a.get("duration", 0) for a in activities if a.get("duration")]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            return SessionMetrics(
                session_id=session_id,
                duration_seconds=duration,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=avg_response_time,
                total_tokens_used=0,  # Would calculate from game generations
                bandwidth_used=0,  # Would calculate from data transfer
            )

        except Exception as e:
            logger.error("Failed to get session metrics", session_id=session_id, error=str(e))
            return None

    async def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """
        Get summary of session activity.

        Args:
            session_id: Session identifier

        Returns:
            SessionSummary object or None
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                return None

            # Calculate duration
            duration_minutes = (
                datetime.utcnow() - session.session_info.created_at
            ).total_seconds() / 60

            # Analyze activities from Redis
            activities = await self._get_session_activities(session_id)
            main_activities = list(set(a.get("activity_type", "unknown") for a in activities))

            # Determine achievements
            achievements = []
            if session.generation_count > 0:
                achievements.append("first_game_created")
            if session.modifications_made > 5:
                achievements.append("active_modifier")
            if session.conversation_messages > 10:
                achievements.append("conversational_user")

            # Identify issues
            issues = []
            error_activities = [a for a in activities if not a.get("success", True)]
            if len(error_activities) > 0:
                issues.append(f"{len(error_activities)} errors encountered")

            return SessionSummary(
                session_id=session_id,
                duration_minutes=duration_minutes,
                games_created=session.generation_count,
                total_modifications=session.modifications_made,
                conversation_turns=session.conversation_messages,
                final_status=session.session_info.status,
                main_activities=main_activities,
                achievements=achievements,
                issues_encountered=issues,
            )

        except Exception as e:
            logger.error("Failed to get session summary", session_id=session_id, error=str(e))
            return None

    async def cleanup_expired_sessions(self) -> Dict[str, Any]:
        """
        Manual cleanup of expired sessions from Redis (rarely needed).

        Note: Redis TTL handles 99% of cleanup automatically. This method is only for:
        - Edge cases where TTL didn't work
        - Manual cleanup operations
        - Corrupted session data removal

        In normal operation, you don't need to call this method.

        Returns:
            Dictionary with cleanup results
        """
        try:
            if not redis_service.client:
                logger.error("Redis client not available for cleanup")
                return {"error": "Redis client not available"}

            # Since we're using Redis TTL, most cleanup is automatic
            # This method is mainly for manual cleanup of edge cases

            # Get all session keys using scan for better performance
            pattern = f"{REDIS_KEYS['SESSION']}*"
            session_keys = []
            cursor = 0

            while True:
                cursor, keys = await redis_service.client.scan(cursor, match=pattern, count=100)
                session_keys.extend(keys)
                if cursor == 0:
                    break

            expired_count = 0
            current_time = datetime.utcnow()

            for key in session_keys:
                try:
                    session_data = await redis_service.get(key)
                    if session_data:
                        session = SessionState.parse_obj(session_data)
                        if session.session_info.expires_at < current_time:
                            session_id = session.session_info.session_id
                            await self._expire_session(session_id)
                            expired_count += 1
                except Exception as e:
                    # If we can't parse the session, remove the corrupted key
                    await redis_service.delete(key)
                    expired_count += 1
                    logger.warning("Removed corrupted session key", key=key, error=str(e))

            logger.info("Session cleanup completed", expired_count=expired_count)

            return {
                "expired_sessions": expired_count,
                "total_session_keys": len(session_keys),
                "cleanup_time": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Session cleanup failed", error=str(e))
            return {"error": str(e)}

    async def get_active_session_count(self) -> int:
        """Get count of active sessions from Redis."""
        try:
            if not redis_service.client:
                logger.error("Redis client not available")
                return 0

            pattern = f"{REDIS_KEYS['SESSION']}*"
            session_keys = []
            cursor = 0

            while True:
                cursor, keys = await redis_service.client.scan(cursor, match=pattern, count=100)
                session_keys.extend(keys)
                if cursor == 0:
                    break

            # Filter out activity keys
            session_keys = [k for k in session_keys if not k.endswith(":activities")]
            return len(session_keys)
        except Exception as e:
            logger.error("Failed to get active session count", error=str(e))
            return 0

    async def get_session_statistics(self) -> Dict[str, Any]:
        """Get overall session statistics from Redis."""
        try:
            active_count = await self.get_active_session_count()

            # Simplified statistics without complex Redis operations
            return {
                "active_sessions": active_count,
                "total_activities": 0,  # Simplified - would calculate from activity keys
                "redis_keys_used": 0,  # Simplified - would scan for activity keys
                "memory_efficient": True,  # No local caching
                "stateless_design": True,  # Fully Redis-dependent
                "container_friendly": True,  # No memory leaks
            }

        except Exception as e:
            logger.error("Failed to get session statistics", error=str(e))
            return {}

    # Private Methods (organized at the end for better readability)

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
            # Log expiration
            await self._log_activity(session_id, "session_expired", {"reason": "timeout"})

            # Remove from Redis
            await redis_service.delete_session(session_id)

            logger.info("Session expired", session_id=session_id)

        except Exception as e:
            logger.error("Failed to expire session", session_id=session_id, error=str(e))

    async def _log_activity(
        self,
        session_id: str,
        activity_type: str,
        details: Dict[str, Any],
        success: bool = True,
        duration: Optional[float] = None,
    ) -> None:
        """Log session activity to Redis using simplified approach."""
        try:
            activity = {
                "session_id": session_id,
                "activity_type": activity_type,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details,
                "duration": duration,
                "success": success,
            }

            # Store activity in Redis as simple key-value with timestamp
            timestamp = int(datetime.utcnow().timestamp())
            activity_key = (
                f"{REDIS_KEYS['SESSION']}activity:{session_id}:{activity_type}:{timestamp}"
            )

            # Use existing Redis service methods
            await redis_service.set(activity_key, activity, ttl=settings.session.ttl * 2)

        except Exception as e:
            logger.error(
                "Failed to log activity",
                session_id=session_id,
                activity_type=activity_type,
                error=str(e),
            )

    async def _get_session_activities(self, session_id: str) -> List[Dict[str, Any]]:
        """Get session activities from Redis using simplified approach."""
        try:
            # Simplified approach - return basic stats instead of full activity list
            # In a real implementation, you'd use a proper time-series database
            return [
                {
                    "activity_type": "session_created",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "duration": 0.1,
                }
            ]
        except Exception as e:
            logger.error("Failed to get session activities", session_id=session_id, error=str(e))
            return []
