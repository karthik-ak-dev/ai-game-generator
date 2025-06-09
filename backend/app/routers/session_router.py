"""
Enterprise-Standard Session Router
Thin router that handles only HTTP concerns and delegates to controllers.
"""

from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from ..controllers.session_controller import SessionController
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError
from ..models.session_models import SessionCreationRequest

logger = structlog.get_logger(__name__)
router = APIRouter()

# Controller instance
session_controller = SessionController()


@router.post("/create")
async def create_session(
    request: Optional[SessionCreationRequest] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> JSONResponse:
    """
    Create a new session.

    Args:
        request: Optional session creation request
        background_tasks: FastAPI background tasks

    Returns:
        JSON response with new session information
    """
    try:
        result = await session_controller.create_session(request)

        # Schedule background cleanup if needed
        if background_tasks and result.data and result.data.get("session_id"):
            background_tasks.add_task(_log_session_creation, result.data["session_id"])

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "error_code": e.error_code, "details": e.details},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/info/{session_id}")
async def get_session_info(session_id: str) -> JSONResponse:
    """
    Get session information.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with session information
    """
    try:
        result = await session_controller.get_session_info(session_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.put("/preferences/{session_id}")
async def update_session_preferences(session_id: str, preferences: Dict[str, Any]) -> JSONResponse:
    """
    Update session preferences.

    Args:
        session_id: Session identifier
        preferences: New preferences

    Returns:
        JSON response with updated preferences
    """
    try:
        result = await session_controller.update_session_preferences(session_id, preferences)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "error_code": e.error_code, "details": e.details},
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/metrics/{session_id}")
async def get_session_metrics(session_id: str) -> JSONResponse:
    """
    Get session metrics and analytics.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with session metrics
    """
    try:
        result = await session_controller.get_session_metrics(session_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.post("/extend/{session_id}")
async def extend_session(session_id: str) -> JSONResponse:
    """
    Extend session expiration.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with extended session info
    """
    try:
        result = await session_controller.extend_session(session_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.delete("/cleanup/{session_id}")
async def cleanup_session(session_id: str) -> JSONResponse:
    """
    Clean up session and associated data.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with cleanup confirmation
    """
    try:
        result = await session_controller.cleanup_session(session_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/summary")
async def get_active_sessions_summary() -> JSONResponse:
    """
    Get summary of active sessions.

    Returns:
        JSON response with active sessions summary
    """
    try:
        result = await session_controller.get_active_sessions_summary()

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


# Background task functions
async def _log_session_creation(session_id: str) -> None:
    """Log session creation in background."""
    try:
        logger.info("Session creation logged", session_id=session_id)
        # Session creation analytics
    except Exception as e:
        logger.error("Session creation logging failed", session_id=session_id, error=str(e))
