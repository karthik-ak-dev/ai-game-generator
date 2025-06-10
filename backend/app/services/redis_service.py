"""
Redis service for caching, session storage, and data persistence.
Production-ready Redis client with connection pooling and error handling.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import redis.asyncio as redis
import structlog

from ..config import settings
from ..utils.constants import REDIS_KEYS

logger = structlog.get_logger(__name__)


class RedisError(Exception):
    """Redis service specific errors."""

    pass


class CircuitBreaker:
    """Circuit breaker for Redis operations."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == "OPEN":
                if (
                    self.last_failure_time
                    and (datetime.utcnow() - self.last_failure_time).total_seconds()
                    > self.recovery_timeout
                ):
                    self.state = "HALF_OPEN"
                else:
                    raise RedisError("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                await self._on_success()
                return result
            except Exception as e:
                await self._on_failure()
                raise e

    async def _on_success(self):
        """Reset circuit breaker on successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    async def _on_failure(self):
        """Handle failure in circuit breaker."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class RedisService:
    """Production Redis client with connection pooling and resilience."""

    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        self._is_connected = False
        self._operation_semaphore = asyncio.Semaphore(100)  # Limit concurrent operations
        self._circuit_breaker = CircuitBreaker()

    async def connect(self) -> bool:
        """
        Establish Redis connection with retry logic and optimized settings.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            # Optimized connection pool settings for production
            self.connection_pool = redis.ConnectionPool.from_url(
                settings.redis.connection_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                socket_connect_timeout=3,
                socket_timeout=3,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )

            self.client = redis.Redis(
                connection_pool=self.connection_pool,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
            )

            # Test connection with timeout
            await asyncio.wait_for(self.client.ping(), timeout=5.0)
            self._is_connected = True

            logger.info(
                "Redis connection established",
                host=settings.redis.host,
                port=settings.redis.port,
            )
            return True

        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self._is_connected = False
            return False

    async def disconnect(self) -> None:
        """Close Redis connection gracefully with cleanup."""
        try:
            if self.client:
                await asyncio.sleep(0.1)
                await self.client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            self._is_connected = False
            logger.info("Redis connection closed gracefully")
        except Exception as e:
            logger.error("Error closing Redis connection", error=str(e))

    async def health_check(self) -> Dict[str, Any]:
        """
        Redis health check.

        Returns:
            Health status dictionary
        """
        if not self._is_connected or not self.client:
            return {
                "status": "unhealthy",
                "message": "Redis not connected",
                "circuit_breaker_state": self._circuit_breaker.state,
            }

        try:
            start_time = time.time()
            await asyncio.wait_for(self.client.ping(), timeout=2.0)
            latency = round((time.time() - start_time) * 1000, 2)  # ms

            return {
                "status": "healthy",
                "message": "Redis connection active",
                "latency": latency,
                "circuit_breaker_state": self._circuit_breaker.state,
            }
        except asyncio.TimeoutError:
            return {
                "status": "unhealthy",
                "message": "Redis ping timeout",
                "circuit_breaker_state": self._circuit_breaker.state,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis error: {str(e)}",
                "circuit_breaker_state": self._circuit_breaker.state,
            }

    @asynccontextmanager
    async def _operation_context(self, operation_name: str):
        """Context manager for tracking operations."""
        async with self._operation_semaphore:
            try:
                yield
            except Exception as e:
                logger.error(f"Redis operation failed: {operation_name}", error=str(e))
                raise

    # Session Management Methods

    async def store_session(
        self, session_id: str, session_data: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """Store session data with optimized serialization."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("store_session"):
            try:
                key = f"{REDIS_KEYS['SESSION']}{session_id}"
                data = json.dumps(session_data, separators=(",", ":"), default=str)
                ttl = ttl or settings.redis.session_ttl

                result = await self._circuit_breaker.call(self.client.setex, key, ttl, data)
                return bool(result)
            except Exception as e:
                logger.error("Failed to store session", session_id=session_id, error=str(e))
                return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data with optimized deserialization."""
        if not self.client:
            logger.error("Redis client not connected")
            return None

        async with self._operation_context("get_session"):
            try:
                key = f"{REDIS_KEYS['SESSION']}{session_id}"
                data = await self._circuit_breaker.call(self.client.get, key)

                if data:
                    return json.loads(data)
                return None
            except json.JSONDecodeError as e:
                logger.error("Session data corrupted", session_id=session_id, error=str(e))
                await self.delete_session(session_id)
                return None
            except Exception as e:
                logger.error("Failed to get session", session_id=session_id, error=str(e))
                return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session data with cleanup."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("delete_session"):
            try:
                key = f"{REDIS_KEYS['SESSION']}{session_id}"
                result = await self._circuit_breaker.call(self.client.delete, key)

                # Also clean up related data
                cleanup_tasks = [
                    self.client.delete(f"{REDIS_KEYS['CONVERSATION_CONTEXT']}{session_id}"),
                ]
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)

                return bool(result)
            except Exception as e:
                logger.error("Failed to delete session", session_id=session_id, error=str(e))
                return False

    # Conversation Context Methods

    async def store_conversation_context(
        self, session_id: str, context_data: Dict[str, Any]
    ) -> bool:
        """Store conversation context with compression for large data."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("store_conversation_context"):
            try:
                key = f"{REDIS_KEYS['CONVERSATION_CONTEXT']}{session_id}"

                # Optimize large conversation histories
                if "conversation_history" in context_data:
                    history = context_data["conversation_history"]
                    if len(history) > 50:  # Limit conversation history size
                        context_data["conversation_history"] = history[-50:]

                data = json.dumps(context_data, separators=(",", ":"), default=str)

                # Use compression for large contexts
                if len(data) > 10000:  # 10KB threshold
                    import gzip

                    data = gzip.compress(data.encode("utf-8"))
                    key = f"{key}:compressed"

                result = await self._circuit_breaker.call(
                    self.client.setex, key, settings.redis.cache_ttl, data
                )
                return bool(result)
            except Exception as e:
                logger.error(
                    "Failed to store conversation context", session_id=session_id, error=str(e)
                )
                return False

    async def get_conversation_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation context with decompression."""
        if not self.client:
            logger.error("Redis client not connected")
            return None

        async with self._operation_context("get_conversation_context"):
            try:
                key = f"{REDIS_KEYS['CONVERSATION_CONTEXT']}{session_id}"
                compressed_key = f"{key}:compressed"

                # Try compressed version first
                data = await self._circuit_breaker.call(self.client.get, compressed_key)
                if data:
                    import gzip

                    data = gzip.decompress(data).decode("utf-8")
                else:
                    # Try uncompressed version
                    data = await self._circuit_breaker.call(self.client.get, key)

                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.error(
                    "Failed to get conversation context", session_id=session_id, error=str(e)
                )
                return None

    # General Cache Methods

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value with intelligent serialization."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("set"):
            try:
                # Intelligent serialization based on data type
                if isinstance(value, (dict, list)):
                    data = json.dumps(value, separators=(",", ":"), default=str)
                elif isinstance(value, (int, float, bool)):
                    data = str(value)
                else:
                    data = str(value)

                if ttl:
                    result = await self._circuit_breaker.call(self.client.setex, key, ttl, data)
                else:
                    result = await self._circuit_breaker.call(self.client.set, key, data)
                return bool(result)
            except Exception as e:
                logger.error("Failed to set cache key", key=key, error=str(e))
                return False

    async def get(self, key: str) -> Optional[Any]:
        """Get value with intelligent deserialization."""
        if not self.client:
            logger.error("Redis client not connected")
            return None

        async with self._operation_context("get"):
            try:
                data = await self._circuit_breaker.call(self.client.get, key)
                if data is None:
                    return None

                # Try JSON parsing first
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    # Return as string if not JSON
                    return data
            except Exception as e:
                logger.error("Failed to get cache key", key=key, error=str(e))
                return None

    async def delete(self, key: str) -> bool:
        """Delete key efficiently."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("delete"):
            try:
                result = await self._circuit_breaker.call(self.client.delete, key)
                return bool(result)
            except Exception as e:
                logger.error("Failed to delete cache key", key=key, error=str(e))
                return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.client:
            logger.error("Redis client not connected")
            return False

        async with self._operation_context("exists"):
            try:
                result = await self._circuit_breaker.call(self.client.exists, key)
                return bool(result)
            except Exception as e:
                logger.error("Failed to check key existence", key=key, error=str(e))
                return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected and circuit breaker is closed."""
        return (
            self._is_connected and self.client is not None and self._circuit_breaker.state != "OPEN"
        )


# Global Redis service instance
redis_service = RedisService()
