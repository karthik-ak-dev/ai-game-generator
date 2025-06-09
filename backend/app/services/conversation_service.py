"""
Conversation service for managing chat context and AI interactions.
Handles context preservation, intent recognition, and conversation flow.
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from ..config import settings
from ..models.chat_models import ChatMessage, ConversationContext
from ..models.game_models import GameState
from ..utils.constants import REDIS_KEYS, MessageType, ModificationType
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class ConversationService:
    """Manages conversation context and chat interactions."""

    def __init__(self):
        self.max_context_length = settings.rate_limit.max_conversation_history

    async def process_message(
        self, session_id: str, message: str, current_game_state: Optional[GameState] = None
    ) -> Dict[str, Any]:
        """
        Process incoming chat message and update conversation context.

        Args:
            session_id: Session identifier
            message: User message
            current_game_state: Current game state if available

        Returns:
            Dictionary with processed message and context
        """
        try:
            # Get or create conversation context
            context = await self.get_conversation_context(session_id)

            # Create chat message
            chat_message = ChatMessage(
                id=f"msg_{int(time.time() * 1000)}",
                session_id=session_id,
                type=MessageType.USER_MESSAGE,
                content=message,
                role="user",
            )

            # Analyze user intent
            intent_analysis = self._analyze_user_intent(message, context)

            # Update conversation context
            context.conversation_history.append(chat_message)
            context.user_intent = intent_analysis["intent"]
            context.modification_type = intent_analysis.get("modification_type")
            context.last_activity = datetime.utcnow()

            # Update game context if provided
            if current_game_state:
                context.current_game_state = {
                    "game_id": current_game_state.game_id,
                    "version": current_game_state.current_version,
                    "features": current_game_state.metadata.features,
                    "game_type": current_game_state.metadata.game_type,
                    "engine": current_game_state.metadata.engine,
                }
                context.active_features = current_game_state.metadata.features

            # Trim context if too long
            context = self._trim_conversation_context(context)

            # Update conversation stage
            context.conversation_stage = self._determine_conversation_stage(context)

            # Cache updated context
            await self._cache_conversation_context(session_id, context)

            logger.info(
                "Message processed",
                session_id=session_id,
                intent=intent_analysis["intent"],
                conversation_length=len(context.conversation_history),
            )

            return {
                "chat_message": chat_message,
                "context": context,
                "intent_analysis": intent_analysis,
                "conversation_stage": context.conversation_stage,
            }

        except Exception as e:
            logger.error("Failed to process message", session_id=session_id, error=str(e))
            raise

    async def add_ai_response(
        self, session_id: str, response: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add AI response to conversation history.

        Args:
            session_id: Session identifier
            response: AI response text
            metadata: Additional response metadata
        """
        try:
            context = await self.get_conversation_context(session_id)

            ai_message = ChatMessage(
                id=f"ai_msg_{int(time.time() * 1000)}",
                session_id=session_id,
                type=MessageType.AI_RESPONSE,
                content=response,
                role="assistant",
                metadata=metadata,
            )

            context.conversation_history.append(ai_message)
            context.last_activity = datetime.utcnow()

            await self._cache_conversation_context(session_id, context)

        except Exception as e:
            logger.error("Failed to add AI response", session_id=session_id, error=str(e))
            raise

    async def get_conversation_context(self, session_id: str) -> ConversationContext:
        """
        Get conversation context for session.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext object
        """
        try:
            # Try to get from Redis first
            context_data = await redis_service.get_conversation_context(session_id)
            if context_data:
                try:
                    return ConversationContext.parse_obj(context_data)
                except Exception as e:
                    logger.error(
                        "Failed to parse conversation context", session_id=session_id, error=str(e)
                    )
                    # Clean up corrupted data
                    await self._delete_conversation_context(session_id)

            # Create new context if not found
            context = ConversationContext(
                session_id=session_id, conversation_history=[], conversation_stage="initial"
            )

            # Store the new context
            await self._cache_conversation_context(session_id, context)

            return context

        except Exception as e:
            logger.error("Failed to get conversation context", session_id=session_id, error=str(e))
            # Return minimal context as fallback
            return ConversationContext(
                session_id=session_id, conversation_history=[], conversation_stage="initial"
            )

    def generate_contextual_prompt(self, context: ConversationContext, current_request: str) -> str:
        """
        Generate context-aware prompt for AI.

        Args:
            context: Conversation context
            current_request: Current user request

        Returns:
            Enhanced prompt with context
        """
        # Build conversation history for context
        history_parts = []
        recent_messages = context.conversation_history[-10:]  # Last 10 messages

        for msg in recent_messages:
            role = "User" if msg.role == "user" else "Assistant"
            history_parts.append(f"{role}: {msg.content}")

        conversation_history = "\n".join(history_parts)

        # Build context information
        context_info = []

        if context.current_game_state:
            game_state = context.current_game_state
            context_info.extend(
                [
                    f"Current Game Type: {game_state.get('game_type', 'unknown')}",
                    f"Game Engine: {game_state.get('engine', 'unknown')}",
                    f"Game Version: {game_state.get('version', 1)}",
                    f"Active Features: {', '.join(game_state.get('features', []))}",
                ]
            )

        if context.user_intent:
            context_info.append(f"User Intent: {context.user_intent}")

        if context.modification_type:
            context_info.append(f"Modification Type: {context.modification_type}")

        # Combine everything
        prompt_parts = [
            "CONVERSATION CONTEXT:",
            conversation_history,
            "",
            "CURRENT GAME CONTEXT:",
            "\n".join(context_info) if context_info else "No active game",
            "",
            "CURRENT REQUEST:",
            current_request,
        ]

        return "\n".join(prompt_parts)

    async def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of conversation for session."""
        try:
            context = await self.get_conversation_context(session_id)

            user_messages = [msg for msg in context.conversation_history if msg.role == "user"]
            ai_messages = [msg for msg in context.conversation_history if msg.role == "assistant"]

            # Analyze conversation patterns
            modification_requests = len(
                [
                    msg
                    for msg in user_messages
                    if any(
                        word in msg.content.lower() for word in ["change", "modify", "add", "fix"]
                    )
                ]
            )

            return {
                "total_messages": len(context.conversation_history),
                "user_messages": len(user_messages),
                "ai_messages": len(ai_messages),
                "modification_requests": modification_requests,
                "current_stage": context.conversation_stage,
                "last_activity": context.last_activity,
                "has_active_game": context.current_game_state is not None,
                "active_features": context.active_features,
            }

        except Exception as e:
            logger.error("Failed to get conversation summary", session_id=session_id, error=str(e))
            return {}

    async def reset_conversation(self, session_id: str) -> None:
        """Reset conversation context for session."""
        try:
            # Remove from Redis
            await self._delete_conversation_context(session_id)

            logger.info("Conversation reset", session_id=session_id)

        except Exception as e:
            logger.error("Failed to reset conversation", session_id=session_id, error=str(e))
            raise

    # Private Methods (organized at the end for better readability)

    async def _delete_conversation_context(self, session_id: str) -> None:
        """Delete conversation context from Redis."""
        try:
            # Delete both compressed and uncompressed versions
            key = f"{REDIS_KEYS['CONVERSATION_CONTEXT']}{session_id}"
            compressed_key = f"{key}:compressed"

            await redis_service.delete(key)
            await redis_service.delete(compressed_key)
        except Exception as e:
            logger.error(
                "Failed to delete conversation context", session_id=session_id, error=str(e)
            )

    def _analyze_user_intent(self, message: str, context: ConversationContext) -> Dict[str, Any]:
        """Analyze user intent from message and context."""
        message_lower = message.lower()

        # Intent detection patterns
        intent_patterns = {
            "create_game": ["create", "make", "generate", "build", "new game"],
            "modify_visual": ["color", "size", "appearance", "look", "visual", "style"],
            "modify_gameplay": ["speed", "difficulty", "controls", "physics", "mechanics"],
            "add_feature": ["add", "include", "new", "implement", "feature"],
            "fix_bug": ["fix", "broken", "error", "not working", "issue", "problem"],
            "ask_question": ["how", "what", "why", "when", "where", "explain"],
            "request_help": ["help", "assistance", "guide", "tutorial"],
        }

        # Calculate intent scores
        intent_scores = {}
        for intent, patterns in intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in message_lower)
            intent_scores[intent] = score / len(patterns)

        # Determine primary intent
        primary_intent = max(intent_scores, key=lambda k: intent_scores[k])
        confidence = intent_scores[primary_intent]

        # Map to modification types
        modification_type_map = {
            "modify_visual": ModificationType.VISUAL_CHANGE,
            "modify_gameplay": ModificationType.GAMEPLAY_CHANGE,
            "add_feature": ModificationType.FEATURE_ADDITION,
            "fix_bug": ModificationType.BUG_FIX,
        }

        result = {"intent": primary_intent, "confidence": confidence, "all_scores": intent_scores}

        if primary_intent in modification_type_map:
            result["modification_type"] = modification_type_map[primary_intent]

        return result

    def _trim_conversation_context(self, context: ConversationContext) -> ConversationContext:
        """Trim conversation context to maintain reasonable size."""
        if len(context.conversation_history) > self.max_context_length:
            # Keep first message (often the initial request) and recent messages
            first_message = context.conversation_history[0]
            recent_messages = context.conversation_history[-(self.max_context_length - 1) :]
            context.conversation_history = [first_message] + recent_messages

        return context

    def _determine_conversation_stage(self, context: ConversationContext) -> str:
        """Determine current stage of conversation."""
        message_count = len(context.conversation_history)

        if message_count == 0:
            return "initial"
        elif message_count == 1:
            return "first_request"
        elif context.current_game_state is None:
            return "creating_game"
        elif message_count < 5:
            return "early_modification"
        else:
            return "advanced_modification"

    async def _cache_conversation_context(
        self, session_id: str, context: ConversationContext
    ) -> None:
        """Cache conversation context in Redis."""
        try:
            context_data = context.dict()
            await redis_service.store_conversation_context(session_id, context_data)
        except Exception as e:
            logger.error(
                "Failed to cache conversation context", session_id=session_id, error=str(e)
            )
