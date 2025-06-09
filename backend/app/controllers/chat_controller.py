"""
Chat Controller - Enterprise Standard
Handles business logic orchestration for chat and conversation operations.
Separates chat business logic from HTTP routing concerns.
"""

# Standard library imports
import time
from typing import Any, Dict

# Third-party imports
import structlog

# Local application imports
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError
from ..models.chat_models import ChatRequest, ConversationContext
from ..models.response_models import create_success_response
from ..services.conversation_service import ConversationService
from ..services.modification_engine import ModificationEngine
from ..services.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class ChatController:
    """
    Enterprise-standard controller for chat operations.
    Orchestrates conversation and modification business logic.
    """

    def __init__(self):
        self.conversation_service = ConversationService()
        self.modification_engine = ModificationEngine()
        self.session_manager = SessionManager()

    async def process_chat_message(self, request: ChatRequest):
        """
        Business logic for processing chat messages.

        Args:
            request: Chat message request

        Returns:
            ApiResponse with AI response and modifications

        Raises:
            ValidationError: For invalid input
            BusinessLogicError: For processing failures
            NotFoundError: For invalid session
        """
        try:
            start_time = time.time()

            logger.info(
                "Processing chat message",
                session_id=request.session_id,
                message_length=len(request.message),
            )

            # Validate request
            await self._validate_chat_request(request)

            # Validate and get session
            session = await self._get_valid_session(request.session_id)

            # Increment message count
            await self.session_manager.increment_message_count(request.session_id)

            # Process message with conversation service
            processed_message = await self.conversation_service.process_message(
                session_id=request.session_id,
                message=request.message,
                # Would load from storage in full implementation
                current_game_state=None,
            )

            # Analyze intent and generate response
            response_data = await self._generate_chat_response(
                session, processed_message, start_time
            )

            # Add AI response to conversation
            await self.conversation_service.add_ai_response(
                session_id=request.session_id,
                response=response_data["response"],
                metadata={
                    "intent": response_data["intent"],
                    "modifications_applied": response_data["modifications_applied"],
                },
            )

            return create_success_response(
                message="Message processed successfully", data=response_data
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Chat message processing failed",
                session_id=request.session_id,
                error=str(e),
            )
            raise BusinessLogicError("Failed to process chat message")

    async def get_conversation_history(self, session_id: str, limit: int = 50):
        """
        Business logic for retrieving conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            ApiResponse with conversation history
        """
        try:
            # Validate session
            await self._get_valid_session(session_id)

            # Get conversation context
            context = await self.conversation_service.get_conversation_context(session_id)

            # Build history response
            history_data = self._build_history_response(context, session_id, limit)

            return create_success_response(
                message="Conversation history retrieved", data=history_data
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Failed to get conversation history",
                session_id=session_id,
                error=str(e),
            )
            raise BusinessLogicError("Failed to retrieve conversation history")

    async def reset_conversation(self, session_id: str):
        """
        Business logic for resetting conversation context.

        Args:
            session_id: Session identifier

        Returns:
            ApiResponse with reset confirmation
        """
        try:
            # Validate session
            await self._get_valid_session(session_id)

            # Reset conversation
            await self.conversation_service.reset_conversation(session_id)

            return create_success_response(
                message="Conversation reset successfully",
                data={"session_id": session_id},
            )

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Failed to reset conversation",
                session_id=session_id,
                error=str(e),
            )
            raise BusinessLogicError("Failed to reset conversation")

    async def get_conversation_summary(self, session_id: str):
        """
        Business logic for getting conversation summary.

        Args:
            session_id: Session identifier

        Returns:
            ApiResponse with conversation summary
        """
        try:
            # Validate session
            await self._get_valid_session(session_id)

            # Get conversation summary
            summary = await self.conversation_service.get_conversation_summary(session_id)

            return create_success_response(message="Conversation summary retrieved", data=summary)

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Failed to get conversation summary",
                session_id=session_id,
                error=str(e),
            )
            raise BusinessLogicError("Failed to retrieve conversation summary")

    async def get_conversation_suggestions(self, session_id: str):
        """
        Business logic for generating conversation suggestions.

        Args:
            session_id: Session identifier

        Returns:
            ApiResponse with conversation suggestions
        """
        try:
            # Validate session
            session = await self._get_valid_session(session_id)

            # Get conversation context
            context = await self.conversation_service.get_conversation_context(session_id)

            # Generate suggestions
            suggestions_data = await self._generate_suggestions(session, context)

            return create_success_response(message="Suggestions retrieved", data=suggestions_data)

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(
                "Failed to get suggestions",
                session_id=session_id,
                error=str(e),
            )
            raise BusinessLogicError("Failed to retrieve suggestions")

    async def validate_websocket_session(self, session_id: str) -> bool:
        """
        Validate session for WebSocket connection.

        Args:
            session_id: Session identifier

        Returns:
            True if session is valid
        """
        try:
            session = await self.session_manager.get_session(session_id)
            return session is not None
        except Exception as e:
            logger.error(
                "WebSocket session validation failed",
                session_id=session_id,
                error=str(e),
            )
            return False

    # Private helper methods

    async def _validate_chat_request(self, request: ChatRequest) -> None:
        """Validate chat request parameters."""
        if not request.message or not request.message.strip():
            raise ValidationError("Message cannot be empty")

        if len(request.message) > 5000:
            raise ValidationError("Message too long (max 5000 characters)")

        if not request.session_id:
            raise ValidationError("Session ID is required")

    async def _get_valid_session(self, session_id: str):
        """Get and validate session exists."""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    async def _generate_chat_response(
        self, session, processed_message: Dict[str, Any], start_time: float
    ) -> Dict[str, Any]:
        """Generate chat response based on processed message."""
        intent_analysis = processed_message["intent_analysis"]

        response_data = {
            "response": "Message received and processed",
            "intent": intent_analysis["intent"],
            "confidence": intent_analysis["confidence"],
            "conversation_stage": processed_message["conversation_stage"],
            "modifications_applied": [],
            "game_updated": False,
            "processing_time": time.time() - start_time,
        }

        # Handle modification requests
        if (
            intent_analysis["intent"]
            in ["modify_visual", "modify_gameplay", "add_feature", "fix_bug"]
            and session.current_game_id
        ):

            try:
                modification_msg = (
                    f"I understand you want to {intent_analysis['intent']}. "
                    "I would apply this modification to your game."
                )
                response_data.update(
                    {
                        "response": modification_msg,
                        "modifications_applied": [f"simulated_{intent_analysis['intent']}"],
                        "game_updated": True,
                    }
                )

                # Increment modification count
                await self.session_manager.increment_modification_count(session.session_id)

            except Exception as e:
                logger.error(
                    "Modification failed",
                    session_id=session.session_id,
                    error=str(e),
                )
                response_data["response"] = (
                    "I encountered an issue applying your modification. "
                    "Please try rephrasing your request."
                )

        elif intent_analysis["intent"] == "create_game":
            response_data["response"] = (
                "I can help you create a game! Please use the game generation "
                "endpoint to create a new game first."
            )

        else:
            # Handle other intents
            response_data["response"] = (
                f"I understand your {intent_analysis['intent']} request. "
                "How can I help you with your game?"
            )

        return response_data

    def _build_history_response(
        self, context: ConversationContext, session_id: str, limit: int
    ) -> Dict[str, Any]:
        """Build conversation history response."""
        # Limit messages
        messages = context.conversation_history[-limit:] if context.conversation_history else []

        return {
            "session_id": session_id,
            "messages": [
                {
                    "id": msg.id,
                    "type": msg.type,
                    "content": msg.content,
                    "role": msg.role,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata,
                }
                for msg in messages
            ],
            "total_messages": len(context.conversation_history),
            "conversation_stage": context.conversation_stage,
            "last_activity": (context.last_activity.isoformat() if context.last_activity else None),
        }

    async def _generate_suggestions(self, session, context: ConversationContext) -> Dict[str, Any]:
        """Generate contextual suggestions."""
        suggestions = []

        if context.conversation_stage == "initial":
            suggestions = [
                "Create a platformer game",
                "Make a space shooter",
                "Build a puzzle game",
                "Generate an arcade game",
            ]
        elif session.current_game_id:
            suggestions = [
                "Change the character color",
                "Add sound effects",
                "Make the game faster",
                "Add more levels",
                "Include power-ups",
            ]
        else:
            suggestions = [
                "Tell me about the game",
                "What can you help me with?",
                "How do I modify my game?",
                "Show me the game controls",
            ]

        return {
            "session_id": session.session_id,
            "suggestions": suggestions,
            "conversation_stage": context.conversation_stage,
            "has_active_game": session.current_game_id is not None,
        }
