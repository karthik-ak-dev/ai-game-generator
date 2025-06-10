"""
Simplified Session Router for AI Game Generator Core Functionality
Handles only essential session operations needed for game generation workflow.
"""

from typing import Optional

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
    Create a new game development session.

    This is typically called automatically when a user starts their first
    conversation with the AI game generator.

    Args:
        request: Optional session creation parameters
        background_tasks: FastAPI background tasks

    Returns:
        JSON response with new session information
    """
    try:
        result = await session_controller.create_session(request)

        # Log session creation in background
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


@router.get("/{session_id}")
async def get_session_state(session_id: str) -> JSONResponse:
    """
    Get current session state including conversation history and current game.

    This is the primary endpoint for retrieving all context needed to
    continue a game development conversation.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with session state, current game, and conversation history
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


@router.delete("/{session_id}")
async def cleanup_session(session_id: str) -> JSONResponse:
    """
    Clean up session and release resources.

    This endpoint allows explicit session cleanup, though sessions
    will also be automatically cleaned up when they expire.

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


# Background task functions
async def _log_session_creation(session_id: str) -> None:
    """Log session creation for monitoring purposes."""
    try:
        logger.info("Session created for game development", session_id=session_id)
    except Exception as e:
        logger.error("Session creation logging failed", session_id=session_id, error=str(e))
