"""
Chat processing utilities for AI Game Generator.
Provides conversation analysis, context management, and message processing functions.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import structlog

from ..config import settings
from ..models.chat_models import ChatMessage, ConversationContext
from ..utils.constants import MessageType, ModificationType

logger = structlog.get_logger(__name__)


class ConversationAnalyzer:
    """Analyzes conversation patterns and user intent."""

    @staticmethod
    def analyze_user_intent(
        message: str, conversation_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Analyze user intent from message content and conversation context.

        Args:
            message: User message to analyze
            conversation_history: Previous conversation messages

        Returns:
            Dictionary with intent analysis results
        """
        message_lower = message.lower()

        # Intent detection patterns
        intent_patterns = {
            "create_game": ["create", "make", "generate", "build", "new game", "start", "begin"],
            "modify_visual": [
                "color",
                "size",
                "appearance",
                "look",
                "visual",
                "style",
                "bigger",
                "smaller",
                "red",
                "blue",
                "green",
                "yellow",
                "purple",
                "orange",
                "pink",
                "black",
                "white",
            ],
            "modify_gameplay": [
                "speed",
                "difficulty",
                "controls",
                "physics",
                "mechanics",
                "faster",
                "slower",
                "easier",
                "harder",
                "jump",
                "movement",
                "gravity",
            ],
            "add_feature": [
                "add",
                "include",
                "new",
                "implement",
                "feature",
                "more",
                "extra",
                "also",
                "coins",
                "powerups",
                "enemies",
                "levels",
                "sound",
                "music",
            ],
            "fix_bug": [
                "fix",
                "broken",
                "error",
                "not working",
                "issue",
                "problem",
                "bug",
                "wrong",
                "doesn't work",
                "glitch",
            ],
            "ask_question": [
                "how",
                "what",
                "why",
                "when",
                "where",
                "explain",
                "tell me",
                "can you",
            ],
            "request_help": [
                "help",
                "assistance",
                "guide",
                "tutorial",
                "stuck",
                "confused",
                "don't know",
            ],
        }

        # Calculate intent scores
        intent_scores = {}
        for intent, patterns in intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in message_lower)
            # Normalize by pattern count
            intent_scores[intent] = score / len(patterns) if patterns else 0

        # Consider conversation context
        if conversation_history:
            context_boost = ConversationAnalyzer._get_context_boost(
                message_lower, conversation_history
            )
            for intent, boost in context_boost.items():
                intent_scores[intent] = intent_scores.get(intent, 0) + boost

        # Determine primary intent
        primary_intent = (
            max(intent_scores, key=intent_scores.get) if intent_scores else "ask_question"
        )
        confidence = intent_scores.get(primary_intent, 0)

        # Map to modification types
        modification_type_map = {
            "modify_visual": ModificationType.VISUAL_CHANGE,
            "modify_gameplay": ModificationType.GAMEPLAY_CHANGE,
            "add_feature": ModificationType.FEATURE_ADDITION,
            "fix_bug": ModificationType.BUG_FIX,
        }

        result = {
            "intent": primary_intent,
            "confidence": min(confidence, 1.0),
            "all_scores": intent_scores,
            "context_aware": len(conversation_history) > 0,
        }

        if primary_intent in modification_type_map:
            result["modification_type"] = modification_type_map[primary_intent]

        return result

    @staticmethod
    def _get_context_boost(
        message: str, conversation_history: List[ChatMessage]
    ) -> Dict[str, float]:
        """Get intent boost based on conversation context."""
        context_boost = {}

        # Recent AI responses indicating current focus
        recent_ai_messages = [msg for msg in conversation_history[-5:] if msg.role == "assistant"]

        for ai_msg in recent_ai_messages:
            ai_content = ai_msg.content.lower()

            # If AI just mentioned colors, boost visual intent
            if any(word in ai_content for word in ["color", "appearance", "visual"]):
                context_boost["modify_visual"] = context_boost.get("modify_visual", 0) + 0.2

            # If AI just mentioned gameplay, boost gameplay intent
            if any(word in ai_content for word in ["speed", "difficulty", "mechanics"]):
                context_boost["modify_gameplay"] = context_boost.get("modify_gameplay", 0) + 0.2

            # If AI just added features, user might want more
            if any(word in ai_content for word in ["added", "implemented", "included"]):
                context_boost["add_feature"] = context_boost.get("add_feature", 0) + 0.1

        return context_boost

    @staticmethod
    def detect_specific_elements(message: str) -> Dict[str, List[str]]:
        """
        Detect specific game elements mentioned in the message.

        Args:
            message: User message to analyze

        Returns:
            Dictionary with detected elements by category
        """
        elements = {"colors": [], "features": [], "objects": [], "actions": [], "numbers": []}

        message_lower = message.lower()

        # Color detection
        color_patterns = {
            "red": ["red", "crimson", "scarlet"],
            "blue": ["blue", "azure", "navy"],
            "green": ["green", "lime", "emerald"],
            "yellow": ["yellow", "gold", "amber"],
            "purple": ["purple", "violet", "magenta"],
            "orange": ["orange", "tangerine"],
            "pink": ["pink", "rose"],
            "black": ["black", "dark"],
            "white": ["white", "bright"],
            "brown": ["brown", "tan"],
        }

        for color, variants in color_patterns.items():
            if any(variant in message_lower for variant in variants):
                elements["colors"].append(color)

        # Feature detection
        feature_keywords = [
            "coins",
            "powerups",
            "enemies",
            "platforms",
            "levels",
            "sound",
            "music",
            "particles",
            "effects",
            "scoring",
            "timer",
            "health",
            "lives",
            "weapons",
        ]

        for feature in feature_keywords:
            if feature in message_lower:
                elements["features"].append(feature)

        # Object detection
        object_keywords = [
            "player",
            "character",
            "ship",
            "car",
            "ball",
            "block",
            "wall",
            "door",
            "flag",
            "star",
            "gem",
            "key",
            "bomb",
            "rocket",
            "laser",
        ]

        for obj in object_keywords:
            if obj in message_lower:
                elements["objects"].append(obj)

        # Action detection
        action_keywords = [
            "jump",
            "shoot",
            "move",
            "run",
            "fly",
            "collect",
            "destroy",
            "build",
            "push",
            "pull",
            "rotate",
            "scale",
            "animate",
        ]

        for action in action_keywords:
            if action in message_lower:
                elements["actions"].append(action)

        # Number extraction
        numbers = re.findall(r"\b\d+\b", message)
        elements["numbers"] = [int(num) for num in numbers]

        return elements


class ConversationContextManager:
    """Manages conversation context and session state."""

    @staticmethod
    def build_contextual_prompt(
        conversation_context: ConversationContext,
        current_request: str,
        game_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build context-aware prompt for AI processing.

        Args:
            conversation_context: Full conversation context
            current_request: Current user request
            game_context: Current game state context

        Returns:
            Enhanced prompt with full context
        """
        # Build conversation history section
        history_parts = []
        recent_messages = conversation_context.conversation_history[-10:]  # Last 10 messages

        for msg in recent_messages:
            role = "User" if msg.role == "user" else "Assistant"
            # Truncate long messages for context efficiency
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            history_parts.append(f"{role}: {content}")

        conversation_history = "\n".join(history_parts)

        # Build game context section
        game_context_parts = []
        if game_context:
            game_context_parts.extend(
                [
                    f"Current Game Type: {game_context.get('game_type', 'unknown')}",
                    f"Game Engine: {game_context.get('engine', 'unknown')}",
                    f"Game Version: {game_context.get('version', 1)}",
                    f"Active Features: {', '.join(game_context.get('features', []))}",
                ]
            )

        game_context_info = (
            "\n".join(game_context_parts) if game_context_parts else "No active game"
        )

        # Build session context
        session_context_parts = []
        if hasattr(conversation_context, "user_intent"):
            session_context_parts.append(f"Detected Intent: {conversation_context.user_intent}")
        if hasattr(conversation_context, "conversation_stage"):
            session_context_parts.append(
                f"Conversation Stage: {conversation_context.conversation_stage}"
            )

        session_context_info = (
            "\n".join(session_context_parts) if session_context_parts else "New conversation"
        )

        # Combine all context
        contextual_prompt = f"""CONVERSATION CONTEXT:
{conversation_history}

GAME CONTEXT:
{game_context_info}

SESSION CONTEXT:
{session_context_info}

CURRENT REQUEST:
{current_request}

Please respond appropriately considering the full context above."""

        return contextual_prompt

    @staticmethod
    def summarize_conversation(conversation_history: List[ChatMessage]) -> Dict[str, Any]:
        """
        Create a summary of the conversation for context compression.

        Args:
            conversation_history: List of chat messages

        Returns:
            Dictionary with conversation summary
        """
        if not conversation_history:
            return {"total_messages": 0, "summary": "No conversation yet"}

        user_messages = [msg for msg in conversation_history if msg.role == "user"]
        ai_messages = [msg for msg in conversation_history if msg.role == "assistant"]

        # Analyze user request patterns
        modification_requests = 0
        creation_requests = 0
        question_requests = 0

        for msg in user_messages:
            content_lower = msg.content.lower()
            if any(word in content_lower for word in ["change", "modify", "make", "add"]):
                modification_requests += 1
            elif any(word in content_lower for word in ["create", "generate", "build"]):
                creation_requests += 1
            elif any(word in content_lower for word in ["how", "what", "why", "?"]):
                question_requests += 1

        # Calculate conversation metrics
        total_messages = len(conversation_history)
        avg_message_length = sum(len(msg.content) for msg in conversation_history) / total_messages

        # Determine conversation phase
        if creation_requests > modification_requests:
            phase = "creation_focused"
        elif modification_requests > 0:
            phase = "modification_focused"
        else:
            phase = "exploratory"

        return {
            "total_messages": total_messages,
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "modification_requests": modification_requests,
            "creation_requests": creation_requests,
            "question_requests": question_requests,
            "avg_message_length": avg_message_length,
            "conversation_phase": phase,
            "duration": ConversationContextManager._calculate_conversation_duration(
                conversation_history
            ),
            "last_activity": conversation_history[-1].timestamp if conversation_history else None,
        }

    @staticmethod
    def _calculate_conversation_duration(conversation_history: List[ChatMessage]) -> float:
        """Calculate conversation duration in minutes."""
        if len(conversation_history) < 2:
            return 0.0

        start_time = conversation_history[0].timestamp
        end_time = conversation_history[-1].timestamp

        duration = (end_time - start_time).total_seconds() / 60
        return round(duration, 2)


class MessageProcessor:
    """Processes and formats chat messages."""

    @staticmethod
    def format_ai_response(
        response_text: str,
        modifications_applied: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format AI response with modification details.

        Args:
            response_text: Base AI response
            modifications_applied: List of modifications made
            metadata: Additional response metadata

        Returns:
            Formatted response string
        """
        formatted_parts = [response_text]

        if modifications_applied:
            if len(modifications_applied) == 1:
                formatted_parts.append(f"\n✓ Applied: {modifications_applied[0]}")
            else:
                formatted_parts.append("\n✓ Applied changes:")
                for mod in modifications_applied:
                    formatted_parts.append(f"  • {mod}")

        if metadata:
            if metadata.get("generation_time"):
                formatted_parts.append(f"\n⏱️ Completed in {metadata['generation_time']:.1f}s")

            if metadata.get("warnings"):
                formatted_parts.append("\n⚠️ Notes:")
                for warning in metadata["warnings"]:
                    formatted_parts.append(f"  • {warning}")

        return "\n".join(formatted_parts)

    @staticmethod
    def extract_code_changes(old_code: str, new_code: str) -> List[str]:
        """
        Extract high-level changes between code versions.

        Args:
            old_code: Original code
            new_code: Modified code

        Returns:
            List of detected changes
        """
        changes = []

        if old_code == new_code:
            return ["No changes detected"]

        # Simple change detection
        old_lines = old_code.split("\n")
        new_lines = new_code.split("\n")

        if len(new_lines) > len(old_lines):
            changes.append(f"Added {len(new_lines) - len(old_lines)} lines of code")
        elif len(new_lines) < len(old_lines):
            changes.append(f"Removed {len(old_lines) - len(new_lines)} lines of code")

        # Check for color changes
        old_colors = re.findall(r"#[0-9a-fA-F]{6}|0x[0-9a-fA-F]{6}", old_code)
        new_colors = re.findall(r"#[0-9a-fA-F]{6}|0x[0-9a-fA-F]{6}", new_code)

        if set(old_colors) != set(new_colors):
            changes.append("Modified color values")

        # Check for new function additions
        old_functions = re.findall(r"function\s+(\w+)", old_code)
        new_functions = re.findall(r"function\s+(\w+)", new_code)

        added_functions = set(new_functions) - set(old_functions)
        if added_functions:
            changes.append(f"Added functions: {', '.join(added_functions)}")

        # Check for variable changes
        old_vars = re.findall(r"(?:const|let|var)\s+(\w+)", old_code)
        new_vars = re.findall(r"(?:const|let|var)\s+(\w+)", new_code)

        added_vars = set(new_vars) - set(old_vars)
        if added_vars:
            changes.append(f"Added variables: {', '.join(list(added_vars)[:3])}")

        return changes if changes else ["Code structure modified"]


class ConversationValidator:
    """Validates conversation flow and message content."""

    @staticmethod
    def validate_message_sequence(conversation_history: List[ChatMessage]) -> Dict[str, Any]:
        """
        Validate conversation message sequence for consistency.

        Args:
            conversation_history: List of chat messages

        Returns:
            Validation results dictionary
        """
        if not conversation_history:
            return {"valid": True, "issues": []}

        issues = []

        # Check for proper alternating pattern
        expected_role = "user"  # Conversations should start with user

        for i, msg in enumerate(conversation_history):
            if msg.role != expected_role:
                issues.append(f"Message {i}: Expected {expected_role}, got {msg.role}")

            # Alternate expected role
            expected_role = "assistant" if expected_role == "user" else "user"

        # Check for timestamp ordering
        for i in range(1, len(conversation_history)):
            if conversation_history[i].timestamp < conversation_history[i - 1].timestamp:
                issues.append(f"Message {i}: Timestamp out of order")

        # Check for reasonable message gaps
        for i in range(1, len(conversation_history)):
            time_gap = (
                conversation_history[i].timestamp - conversation_history[i - 1].timestamp
            ).total_seconds()
            if time_gap > 3600:  # 1 hour gap
                issues.append(f"Message {i}: Large time gap ({time_gap/60:.1f} minutes)")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message_count": len(conversation_history),
            "time_span": ConversationContextManager._calculate_conversation_duration(
                conversation_history
            ),
        }

    @staticmethod
    def detect_conversation_loops(
        conversation_history: List[ChatMessage], threshold: int = 3
    ) -> List[str]:
        """
        Detect if user is repeating similar requests.

        Args:
            conversation_history: List of chat messages
            threshold: Number of similar messages to trigger detection

        Returns:
            List of detected loop patterns
        """
        if len(conversation_history) < threshold * 2:
            return []

        user_messages = [msg for msg in conversation_history if msg.role == "user"]

        # Group similar messages
        similar_groups = {}

        for msg in user_messages:
            # Simple similarity check based on key words
            key_words = set(re.findall(r"\b\w+\b", msg.content.lower()))
            key_words = {word for word in key_words if len(word) > 3}  # Filter short words

            # Find similar existing groups
            matched_group = None
            for group_key, group_messages in similar_groups.items():
                group_words = set(re.findall(r"\b\w+\b", group_key.lower()))
                overlap = len(key_words & group_words) / max(len(key_words | group_words), 1)

                if overlap > 0.5:  # 50% word overlap
                    matched_group = group_key
                    break

            if matched_group:
                similar_groups[matched_group].append(msg.content)
            else:
                similar_groups[msg.content] = [msg.content]

        # Detect loops
        loops = []
        for group_key, messages in similar_groups.items():
            if len(messages) >= threshold:
                loops.append(
                    f"User repeated similar request {len(messages)} times: '{group_key[:50]}...'"
                )

        return loops
