"""
Health Controller - Enterprise Standard
Handles business logic orchestration for system health monitoring.
Separates health check business logic from HTTP routing concerns.
"""

# Standard library imports
from datetime import datetime

# Third-party imports
import structlog

# Local application imports
from ..config import settings
from ..exceptions import BusinessLogicError
from ..models.response_models import SuccessResponse, create_success_response

logger = structlog.get_logger(__name__)


class HealthController:
    """
    Enterprise-standard controller for health monitoring operations.
    Orchestrates system health checks and monitoring.
    """

    async def get_basic_health(self) -> SuccessResponse:
        """
        Business logic for basic health check.

        Returns:
            SuccessResponse with basic health status
        """
        try:
            health_data = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": settings.app.app_version,
                "environment": settings.app.environment,
                "service": "AI Game Generator Backend",
            }

            return create_success_response(message="Service is healthy", data=health_data)

        except Exception as e:
            logger.error("Basic health check failed", error=str(e))
            raise BusinessLogicError("Health check failed")
