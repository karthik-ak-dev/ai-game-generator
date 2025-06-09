"""
Enterprise-Standard Template Router
Thin router that handles only HTTP concerns and delegates to controllers.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import JSONResponse

from ..controllers.template_controller import TemplateController
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError
from ..models.template_models import TemplateSearchRequest
from ..utils.constants import GameType

logger = structlog.get_logger(__name__)
router = APIRouter()

# Controller instance
template_controller = TemplateController()


@router.get("/search")
async def search_templates(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Template category"),
    difficulty: Optional[str] = Query(None, description="Difficulty level"),
    engine: Optional[str] = Query(None, description="Game engine"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> JSONResponse:
    """
    Search templates based on criteria.

    Args:
        query: Search query
        category: Template category filter
        difficulty: Difficulty level filter
        engine: Game engine filter
        tags: Comma-separated tags
        limit: Results limit
        offset: Results offset

    Returns:
        JSON response with search results
    """
    try:
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None

        # Convert limit/offset to page/page_size
        page = (offset // limit) + 1
        page_size = limit

        # Convert category string to GameType if valid
        game_type = None
        if category:
            try:
                game_type = GameType(category)
            except ValueError:
                # Invalid category, leave as None
                pass

        # Create search request
        search_request = TemplateSearchRequest(
            query=query,
            game_type=game_type,
            difficulty=difficulty,
            engine=engine,
            tags=tag_list,
            page=page,
            page_size=page_size,
        )

        result = await template_controller.search_templates(search_request)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

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


@router.get("/{template_id}")
async def get_template(template_id: str) -> JSONResponse:
    """
    Get template by ID.

    Args:
        template_id: Template identifier

    Returns:
        JSON response with template information
    """
    try:
        result = await template_controller.get_template_by_id(template_id)

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


@router.get("/categories/list")
async def get_template_categories() -> JSONResponse:
    """
    Get available template categories.

    Returns:
        JSON response with template categories
    """
    try:
        result = await template_controller.get_template_categories()

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/{template_id}/validate")
async def validate_template(template_id: str) -> JSONResponse:
    """
    Validate a template for security and quality.

    Args:
        template_id: Template identifier

    Returns:
        JSON response with validation results
    """
    try:
        result = await template_controller.validate_template(template_id)

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


@router.get("/featured/list")
async def get_featured_templates(
    limit: int = Query(10, ge=1, le=50, description="Number of featured templates")
) -> JSONResponse:
    """
    Get featured templates.

    Args:
        limit: Maximum number of templates to return

    Returns:
        JSON response with featured templates
    """
    try:
        result = await template_controller.get_featured_templates(limit)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


@router.get("/{template_id}/analytics")
async def get_template_analytics(template_id: str) -> JSONResponse:
    """
    Get template analytics and usage statistics.

    Args:
        template_id: Template identifier

    Returns:
        JSON response with template analytics
    """
    try:
        result = await template_controller.get_template_analytics(template_id)

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


@router.post("/{template_id}/usage/{session_id}")
async def record_template_usage(
    template_id: str, session_id: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Record template usage for analytics.

    Args:
        template_id: Template identifier
        session_id: Session identifier
        background_tasks: FastAPI background tasks

    Returns:
        JSON response with usage confirmation
    """
    try:
        result = await template_controller.record_template_usage(template_id, session_id)

        # Schedule background analytics
        background_tasks.add_task(_log_template_analytics, template_id, session_id)

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result.dict())

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "error_code": e.error_code},
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "error_code": e.error_code},
        )


# Background task functions
async def _log_template_analytics(template_id: str, session_id: str) -> None:
    """Log template usage analytics in background."""
    try:
        logger.info(
            "Template usage analytics logged", template_id=template_id, session_id=session_id
        )
        # Template usage analytics implementation
    except Exception as e:
        logger.error(
            "Template analytics logging failed",
            template_id=template_id,
            session_id=session_id,
            error=str(e),
        )
