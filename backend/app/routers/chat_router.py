"""
Core Chat Router for AI Game Generator
Handles essential chat operations and real-time WebSocket communication.
"""

import json
from typing import Any, Dict

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse

from ..controllers.chat_controller import ChatController
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError
from ..models.chat_models import ChatRequest

logger = structlog.get_logger(__name__)
router = APIRouter()

# Controller instance
chat_controller = ChatController()


class ConnectionManager:
    """WebSocket connection manager for real-time chat."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept WebSocket connection and store it."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connected", session_id=session_id)

    def disconnect(self, session_id: str):
        """Remove WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("WebSocket disconnected", session_id=session_id)

    async def send_message(self, message: Dict[str, Any], session_id: str):
        """Send message to specific session."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(
                    "Failed to send WebSocket message", session_id=session_id, error=str(e)
                )
                self.disconnect(session_id)


# Global connection manager
manager = ConnectionManager()


@router.post("/message")
async def send_chat_message(
    request: ChatRequest, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Send a chat message for game modification.

    Args:
        request: Chat message request
        background_tasks: FastAPI background tasks

    Returns:
        JSON response with AI response and modifications
    """
    try:
        result = await chat_controller.process_chat_message(request)

        # Send WebSocket notification if connected
        background_tasks.add_task(
            _notify_websocket, request.session_id, {"type": "chat_response", "data": result.data}
        )

        # Background analytics with proper null handling
        if result.data:
            intent = result.data.get("intent", "unknown")
            processing_time = result.data.get("processing_time", 0.0)
            background_tasks.add_task(
                _log_chat_analytics,
                request.session_id,
                str(intent) if intent is not None else "unknown",
                float(processing_time) if processing_time is not None else 0.0,
            )

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


@router.get("/history/{session_id}")
async def get_conversation_history(
    session_id: str, limit: int = Query(50, ge=1, le=200, description="Maximum messages to return")
) -> JSONResponse:
    """
    Get conversation history for a session.

    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return

    Returns:
        JSON response with conversation history
    """
    try:
        result = await chat_controller.get_conversation_history(session_id, limit)

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


@router.post("/reset/{session_id}")
async def reset_conversation(session_id: str) -> JSONResponse:
    """
    Reset conversation context for a session.

    Args:
        session_id: Session identifier

    Returns:
        JSON response with reset confirmation
    """
    try:
        result = await chat_controller.reset_conversation(session_id)

        # Notify via WebSocket
        await _notify_websocket(
            session_id,
            {"type": "conversation_reset", "data": {"message": "Conversation has been reset"}},
        )

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


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat communication.

    Args:
        websocket: WebSocket connection
        session_id: Session identifier
    """
    try:
        # Validate session through controller
        is_valid = await chat_controller.validate_websocket_session(session_id)
        if not is_valid:
            await websocket.close(code=4004, reason="Invalid session")
            return

        await manager.connect(websocket, session_id)

        # Send connection confirmation
        await websocket.send_json(
            {
                "type": "connection",
                "data": {"message": "Connected to chat", "session_id": session_id},
            }
        )

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()

                # Handle different message types
                if data.get("type") == "chat_message":
                    await _handle_websocket_chat_message(data, session_id)

                elif data.get("type") == "heartbeat":
                    await websocket.send_json({"type": "heartbeat", "data": {"status": "alive"}})

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected normally", session_id=session_id)

    except Exception as e:
        logger.error("WebSocket error", session_id=session_id, error=str(e))

    finally:
        manager.disconnect(session_id)


# Helper functions


async def _handle_websocket_chat_message(data: Dict[str, Any], session_id: str):
    """Handle chat message received via WebSocket."""
    try:
        message_content = data.get("message", "")

        # Create chat request
        chat_request = ChatRequest(session_id=session_id, message=message_content)

        # Process through controller
        result = await chat_controller.process_chat_message(chat_request)

        # Send response back through WebSocket
        response = {"type": "chat_response", "data": result.data}

        await manager.send_message(response, session_id)

    except Exception as e:
        logger.error("WebSocket chat message handling failed", session_id=session_id, error=str(e))

        # Send error response
        error_response = {
            "type": "error",
            "data": {"message": "Failed to process message", "error": str(e)},
        }

        await manager.send_message(error_response, session_id)


async def _notify_websocket(session_id: str, message: Dict[str, Any]):
    """Send notification via WebSocket if connected."""
    try:
        await manager.send_message(message, session_id)
    except Exception as e:
        logger.debug("WebSocket notification failed", session_id=session_id, error=str(e))


async def _log_chat_analytics(session_id: str, intent: str, processing_time: float):
    """Log chat analytics in background."""
    try:
        logger.info(
            "Chat analytics logged",
            session_id=session_id,
            intent=intent,
            processing_time=processing_time,
        )
    except Exception as e:
        logger.error("Chat analytics logging failed", session_id=session_id, error=str(e))
