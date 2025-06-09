"""
Enterprise-Standard Health Router
Thin router that handles only HTTP concerns and delegates to controllers.
"""

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from ..controllers.health_controller import HealthController
from ..exceptions import BusinessLogicError

logger = structlog.get_logger(__name__)
router = APIRouter()

# Controller instance
health_controller = HealthController()


@router.get("/")
async def basic_health_check() -> JSONResponse:
    """
    Basic health check endpoint.

    Returns:
        JSON response with basic health status
    """
    try:
        result = await health_controller.get_basic_health()

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )
