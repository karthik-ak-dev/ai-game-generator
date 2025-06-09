"""
Enterprise-Standard Game Router
Thin router that handles only HTTP concerns and delegates to controllers.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from ..controllers.game_controller import GameController
from ..exceptions import BusinessLogicError, ValidationError
from ..models.game_models import GameGenerationRequest

logger = structlog.get_logger(__name__)
router = APIRouter()

# Controller instance
game_controller = GameController()


@router.post("/generate")
async def generate_game(
    request: GameGenerationRequest, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Generate a new game from natural language description.

    Args:
        request: Game generation request
        background_tasks: FastAPI background tasks

    Returns:
        JSON response with generated game
    """
    try:
        # Delegate to controller
        result = await game_controller.create_game(request)

        # Schedule background analytics logging
        if result.data and result.data.get("session_id"):
            background_tasks.add_task(_log_analytics, result.data["session_id"])

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


@router.get("/info/{session_id}/{game_id}")
async def get_game_info(session_id: str, game_id: str) -> JSONResponse:
    """
    Get information about a specific game.

    Args:
        session_id: Session identifier
        game_id: Game identifier

    Returns:
        JSON response with game information
    """
    try:
        result = await game_controller.get_game_info(session_id, game_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/validate/{session_id}/{game_id}")
async def validate_game(session_id: str, game_id: str) -> JSONResponse:
    """
    Validate a game's code for security and quality.

    Args:
        session_id: Session identifier
        game_id: Game identifier

    Returns:
        JSON response with validation results
    """
    try:
        result = await game_controller.validate_game_code(session_id, game_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/analytics/{session_id}")
async def get_game_analytics(session_id: str) -> JSONResponse:
    """
    Get analytics for games in a session.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with analytics data
    """
    try:
        result = await game_controller.get_session_analytics(session_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


# Background task function
async def _log_analytics(session_id: str) -> None:
    """Log analytics in background task."""
    try:
        logger.info("Logging game generation analytics", session_id=session_id)
        # Analytics logging implementation
    except Exception as e:
        logger.error("Analytics logging failed", session_id=session_id, error=str(e))
