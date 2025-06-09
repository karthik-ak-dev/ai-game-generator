"""
Prompt engine for managing AI prompts and game generation strategies.
Handles prompt templating, context building, and conversation flow management.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ..config import settings
from ..models.chat_models import ChatMessage, ConversationContext
from ..models.game_models import GameGenerationRequest, GameState
from ..utils.constants import (
    AI_PROMPTS,
    CONVERSATION_PROMPTS,
    DIFFICULTY_LEVELS,
    ENGINE_TYPES,
    MODIFICATION_PROMPTS,
    GameType,
)

logger = structlog.get_logger(__name__)


class PromptEngine:
    """Manages AI prompt generation and conversation strategies."""

    def __init__(self):
        self.system_prompts = AI_PROMPTS
        self.conversation_prompts = CONVERSATION_PROMPTS
        self.modification_prompts = MODIFICATION_PROMPTS

        # Maximum token limits for different contexts
        self.max_tokens = {
            "system": 1000,
            "context": 2000,
            "conversation": 1500,
            "generation": 4000,
            "modification": 3000,
        }

    def build_game_generation_prompt(
        self,
        request: GameGenerationRequest,
        conversation_context: Optional[ConversationContext] = None,
    ) -> str:
        """
        Build prompt for game generation.

        Args:
            request: Game generation request
            conversation_context: Optional conversation context

        Returns:
            Complete prompt for AI
        """
        try:
            # Start with system prompt
            system_prompt = self._get_system_prompt("game_generation")

            # Build context section
            context_section = self._build_context_section(request, conversation_context)

            # Build requirements section
            requirements_section = self._build_requirements_section(request)

            # Build example section
            example_section = self._get_example_section(request.game_type)

            # Build main request
            main_request = self._build_main_request(request)

            # Combine all sections
            prompt_parts = [
                system_prompt,
                context_section,
                requirements_section,
                example_section,
                main_request,
            ]

            full_prompt = "\n\n".join(filter(None, prompt_parts))

            logger.debug(
                "Game generation prompt built",
                prompt_length=len(full_prompt),
                game_type=request.game_type,
                engine=request.engine,
            )

            return full_prompt

        except Exception as e:
            logger.error("Failed to build generation prompt", error=str(e))
            return self._get_fallback_generation_prompt(request)

    def build_modification_prompt(
        self,
        request_message: str,
        current_game_code: str,
        conversation_context: ConversationContext,
        modification_type: str,
    ) -> str:
        """
        Build prompt for game modification.

        Args:
            request_message: User modification request
            current_game_code: Current game code
            conversation_context: Conversation context
            modification_type: Type of modification

        Returns:
            Complete modification prompt
        """
        try:
            # Get appropriate system prompt
            system_prompt = self._get_system_prompt("game_modification")

            # Build conversation context
            conversation_section = self._build_conversation_section(conversation_context)

            # Build current game context
            game_context_section = self._build_game_context_section(current_game_code)

            # Build modification instructions
            modification_section = self._build_modification_section(
                request_message, modification_type
            )

            # Build constraints
            constraints_section = self._get_modification_constraints()

            # Combine sections
            prompt_parts = [
                system_prompt,
                conversation_section,
                game_context_section,
                modification_section,
                constraints_section,
            ]

            full_prompt = "\n\n".join(filter(None, prompt_parts))

            logger.debug(
                "Modification prompt built",
                prompt_length=len(full_prompt),
                modification_type=modification_type,
            )

            return full_prompt

        except Exception as e:
            logger.error("Failed to build modification prompt", error=str(e))
            return self._get_fallback_modification_prompt(request_message)

    def build_conversation_prompt(
        self, message: str, conversation_context: ConversationContext, intent: str
    ) -> str:
        """
        Build prompt for conversational responses.

        Args:
            message: User message
            conversation_context: Conversation context
            intent: Detected user intent

        Returns:
            Conversation prompt
        """
        try:
            # Get conversation system prompt
            system_prompt = self._get_system_prompt("conversation")

            # Build context section
            context_section = self._build_conversation_section(conversation_context)

            # Build intent-specific instructions
            intent_section = self._build_intent_section(intent)

            # Build user message section
            message_section = f"USER MESSAGE:\n{message}"

            # Build response guidelines
            guidelines_section = self._get_conversation_guidelines(intent)

            # Combine sections
            prompt_parts = [
                system_prompt,
                context_section,
                intent_section,
                message_section,
                guidelines_section,
            ]

            full_prompt = "\n\n".join(filter(None, prompt_parts))

            return full_prompt

        except Exception as e:
            logger.error("Failed to build conversation prompt", error=str(e))
            return self._get_fallback_conversation_prompt(message)

    def optimize_prompt_length(self, prompt: str, max_tokens: int) -> str:
        """
        Optimize prompt length to fit within token limits.

        Args:
            prompt: Original prompt
            max_tokens: Maximum tokens allowed

        Returns:
            Optimized prompt
        """
        try:
            # Rough token estimation (1 token ≈ 4 characters)
            estimated_tokens = len(prompt) // 4

            if estimated_tokens <= max_tokens:
                return prompt

            # Calculate target length
            target_length = max_tokens * 4

            # Split into sections
            sections = prompt.split("\n\n")

            # Prioritize sections (system prompt, main request are highest priority)
            priority_sections = []
            optional_sections = []

            for section in sections:
                if any(keyword in section for keyword in ["SYSTEM:", "REQUEST:", "INSTRUCTION:"]):
                    priority_sections.append(section)
                else:
                    optional_sections.append(section)

            # Build optimized prompt
            optimized_parts = priority_sections.copy()
            current_length = sum(len(part) for part in optimized_parts)

            # Add optional sections if space allows
            for section in optional_sections:
                if current_length + len(section) + 4 <= target_length:  # +4 for separators
                    optimized_parts.append(section)
                    current_length += len(section) + 4
                else:
                    break

            optimized_prompt = "\n\n".join(optimized_parts)

            logger.debug(
                "Prompt optimized",
                original_length=len(prompt),
                optimized_length=len(optimized_prompt),
                max_tokens=max_tokens,
            )

            return optimized_prompt

        except Exception as e:
            logger.error("Failed to optimize prompt", error=str(e))
            return prompt[: max_tokens * 4]  # Fallback truncation

    def _get_system_prompt(self, prompt_type: str) -> str:
        """Get system prompt for specific type."""
        try:
            return self.system_prompts.get(prompt_type, self.system_prompts.get("default", ""))
        except Exception:
            return "You are an AI assistant that helps create and modify HTML5 games."

    def _build_context_section(
        self, request: GameGenerationRequest, conversation_context: Optional[ConversationContext]
    ) -> str:
        """Build context section for generation prompt."""
        context_parts = []

        # Add conversation context if available
        if conversation_context and conversation_context.conversation_history:
            recent_messages = conversation_context.conversation_history[-3:]  # Last 3 messages
            context_parts.append("CONVERSATION HISTORY:")
            for msg in recent_messages:
                role = "User" if msg.role == "user" else "Assistant"
                context_parts.append(f"{role}: {msg.content[:200]}...")

        # Add session info
        if hasattr(request, "session_id") and request.session_id:
            context_parts.append(f"Session ID: {request.session_id}")

        return "\n".join(context_parts) if context_parts else ""

    def _build_requirements_section(self, request: GameGenerationRequest) -> str:
        """Build requirements section for generation."""
        requirements = []

        requirements.append("GAME REQUIREMENTS:")
        requirements.append(f"- Game Type: {request.game_type or 'arcade'}")
        requirements.append(f"- Engine: {request.engine or 'phaser'}")
        requirements.append(f"- Difficulty: {request.difficulty or 'beginner'}")

        if request.features:
            requirements.append(f"- Features: {', '.join(request.features)}")

        # Add technical requirements
        requirements.extend(
            [
                "- Must be a complete, playable HTML5 game",
                "- Include proper HTML structure with DOCTYPE",
                "- Use responsive design principles",
                "- Include clear game instructions",
                "- Implement basic game loop and controls",
            ]
        )

        return "\n".join(requirements)

    def _get_example_section(self, game_type: Optional[str]) -> str:
        """Get example section based on game type."""
        if not game_type:
            return ""

        example_prompts = {
            "platformer": "Create a side-scrolling platformer with jumping mechanics and obstacles.",
            "shooter": "Create a space shooter with moving enemies and projectiles.",
            "puzzle": "Create a puzzle game with matching or arrangement mechanics.",
            "arcade": "Create a classic arcade-style game with simple controls.",
            "racing": "Create a racing game with vehicle controls and tracks.",
            "rpg": "Create an RPG with character progression and turn-based combat.",
        }

        example = example_prompts.get(game_type.lower())
        if example:
            return f"EXAMPLE REQUEST:\n{example}"

        return ""

    def _build_main_request(self, request: GameGenerationRequest) -> str:
        """Build main request section."""
        main_parts = [
            "MAIN REQUEST:",
            f"Create a {request.game_type or 'game'} based on this description:",
            f'"{request.prompt}"',
            "",
            "Please provide a complete HTML5 game that includes:",
            "1. Complete HTML structure with all necessary elements",
            "2. Embedded CSS for styling and layout",
            "3. JavaScript game logic with proper game loop",
            "4. User controls and game mechanics",
            "5. Win/lose conditions and scoring",
            "6. Clear visual feedback and game states",
        ]

        return "\n".join(main_parts)

    def _build_conversation_section(self, context: ConversationContext) -> str:
        """Build conversation history section."""
        if not context or not context.conversation_history:
            return ""

        history_parts = ["CONVERSATION HISTORY:"]

        # Get recent messages (last 5)
        recent_messages = context.conversation_history[-5:]

        for msg in recent_messages:
            role = "User" if msg.role == "user" else "Assistant"
            content = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
            history_parts.append(f"{role}: {content}")

        return "\n".join(history_parts)

    def _build_game_context_section(self, game_code: str) -> str:
        """Build current game context section."""
        # Extract key information from game code
        game_info = self._analyze_game_code(game_code)

        context_parts = [
            "CURRENT GAME CONTEXT:",
            f"- Game type: {game_info.get('type', 'unknown')}",
            f"- Engine: {game_info.get('engine', 'unknown')}",
            f"- Code size: {len(game_code)} characters",
            f"- Features detected: {', '.join(game_info.get('features', []))}",
        ]

        return "\n".join(context_parts)

    def _build_modification_section(self, message: str, modification_type: str) -> str:
        """Build modification instructions section."""
        modification_parts = [
            "MODIFICATION REQUEST:",
            f"Type: {modification_type}",
            f"User request: {message}",
            "",
            "INSTRUCTIONS:",
            "1. Analyze the current game code",
            "2. Understand the user's modification request",
            "3. Apply the changes while preserving existing functionality",
            "4. Ensure the modified game remains playable",
            "5. Test that the changes work as expected",
        ]

        return "\n".join(modification_parts)

    def _build_intent_section(self, intent: str) -> str:
        """Build intent-specific instructions."""
        intent_instructions = {
            "create_game": "The user wants to create a new game. Guide them through the process.",
            "modify_visual": "The user wants to change visual aspects. Focus on colors, sizes, and appearance.",
            "modify_gameplay": "The user wants to change gameplay mechanics. Focus on rules and interactions.",
            "add_feature": "The user wants to add new features. Suggest compatible additions.",
            "fix_bug": "The user reported an issue. Help identify and fix the problem.",
            "ask_question": "The user has a question. Provide helpful and informative answers.",
            "request_help": "The user needs assistance. Offer guidance and support.",
        }

        instruction = intent_instructions.get(intent, "Assist the user with their request.")
        return f"USER INTENT: {intent}\nINSTRUCTION: {instruction}"

    def _get_modification_constraints(self) -> str:
        """Get modification constraints and guidelines."""
        return """MODIFICATION CONSTRAINTS:
- Preserve existing game functionality
- Maintain code structure and organization
- Ensure changes are compatible with the current engine
- Keep the game playable and responsive
- Validate that modifications don't break the game
- Provide clear explanations of changes made"""

    def _get_conversation_guidelines(self, intent: str) -> str:
        """Get conversation guidelines based on intent."""
        base_guidelines = """RESPONSE GUIDELINES:
- Be helpful and conversational
- Provide clear and actionable advice
- Ask clarifying questions when needed
- Explain technical concepts simply
- Encourage experimentation and learning"""

        intent_specific = {
            "create_game": "\n- Guide through game creation process step by step",
            "modify_visual": "\n- Focus on visual design principles and aesthetics",
            "modify_gameplay": "\n- Explain game mechanics and balance considerations",
            "add_feature": "\n- Suggest complementary features and implementations",
            "fix_bug": "\n- Help diagnose issues and provide debugging steps",
        }

        return base_guidelines + intent_specific.get(intent, "")

    def _analyze_game_code(self, code: str) -> Dict[str, Any]:
        """Analyze game code to extract information."""
        info = {"type": "unknown", "engine": "unknown", "features": []}

        try:
            code_lower = code.lower()

            # Detect engine
            if "phaser" in code_lower:
                info["engine"] = "phaser"
            elif "three.js" in code_lower or "three" in code_lower:
                info["engine"] = "three"
            elif "p5.js" in code_lower or "p5" in code_lower:
                info["engine"] = "p5"
            elif "canvas" in code_lower:
                info["engine"] = "canvas"

            # Detect game type
            if any(word in code_lower for word in ["platform", "jump", "gravity"]):
                info["type"] = "platformer"
            elif any(word in code_lower for word in ["shoot", "bullet", "enemy"]):
                info["type"] = "shooter"
            elif any(word in code_lower for word in ["puzzle", "match", "tile"]):
                info["type"] = "puzzle"
            elif any(word in code_lower for word in ["race", "car", "speed"]):
                info["type"] = "racing"

            # Detect features
            features = []
            if "score" in code_lower:
                features.append("scoring")
            if "sound" in code_lower or "audio" in code_lower:
                features.append("audio")
            if "level" in code_lower:
                features.append("levels")
            if "collision" in code_lower:
                features.append("collision_detection")
            if "animation" in code_lower:
                features.append("animations")

            info["features"] = features

        except Exception as e:
            logger.error("Failed to analyze game code", error=str(e))

        return info

    def _get_fallback_generation_prompt(self, request: GameGenerationRequest) -> str:
        """Get fallback prompt for generation."""
        return f"""Create a simple {request.game_type or 'arcade'} game based on this description:
"{request.prompt}"

Please provide a complete HTML5 game with embedded CSS and JavaScript."""

    def _get_fallback_modification_prompt(self, message: str) -> str:
        """Get fallback prompt for modification."""
        return f"Please modify the game based on this request: {message}"

    def _get_fallback_conversation_prompt(self, message: str) -> str:
        """Get fallback prompt for conversation."""
        return f"Please respond to this message in a helpful way: {message}"
