"""
Game Router for Core AI Game Generation Functionality
Handles only essential game operations needed for core workflow.
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

        # Schedule background logging
        if result.data and result.data.get("session_id"):
            background_tasks.add_task(_log_game_generation, result.data["session_id"])

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


# Background task function
async def _log_game_generation(session_id: str) -> None:
    """Log game generation for monitoring purposes."""
    try:
        logger.info("Game generation completed", session_id=session_id)
    except Exception as e:
        logger.error("Game generation logging failed", session_id=session_id, error=str(e))
