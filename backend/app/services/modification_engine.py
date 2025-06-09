"""
Modification engine for handling incremental game modifications.
Applies targeted changes to existing games while preserving functionality.
"""

import difflib
import time
from datetime import datetime
from typing import Any, Dict, List

import structlog

from ..models.chat_models import ConversationContext
from ..models.game_models import GameModificationRequest, GameState, GameVersion
from ..services.ai_service import AIService
from ..services.conversation_service import ConversationService
from ..utils.code_utils import CodeAnalyzer, HTMLParser, JavaScriptParser
from ..utils.validation import validator

logger = structlog.get_logger(__name__)


class ModificationError(Exception):
    """Modification specific errors."""

    pass


class ModificationEngine:
    """Handles game modifications and code changes."""

    def __init__(self):
        self.ai_service = AIService()
        self.conversation_service = ConversationService()
        self.html_parser = HTMLParser()
        self.js_parser = JavaScriptParser()
        self.code_analyzer = CodeAnalyzer()

    async def apply_modification(
        self,
        request: GameModificationRequest,
        current_game_state: GameState,
        conversation_context: ConversationContext,
    ) -> Dict[str, Any]:
        """
        Apply modification to existing game.

        Args:
            request: Modification request
            current_game_state: Current game state
            conversation_context: Conversation context

        Returns:
            Dictionary with modification results
        """
        start_time = time.time()

        try:
            logger.info(
                "Starting game modification",
                session_id=request.session_id,
                modification_type=request.modification_type,
                game_version=current_game_state.current_version,
            )

            # Analyze modification intent
            modification_analysis = self._analyze_modification_request(
                request.message, current_game_state
            )

            # Apply modification based on type
            if modification_analysis["strategy"] == "targeted_change":
                result = await self._apply_targeted_modification(
                    request, current_game_state, conversation_context, modification_analysis
                )
            elif modification_analysis["strategy"] == "ai_regeneration":
                result = await self._apply_ai_modification(
                    request, current_game_state, conversation_context
                )
            else:
                result = await self._apply_fallback_modification(
                    request, current_game_state, conversation_context
                )

            # Create new version if code changed
            if result["code_changed"]:
                new_version = await self._create_new_version(
                    current_game_state, result, request.message
                )

                # Update game state
                current_game_state.code = result["modified_code"]
                current_game_state.current_version = new_version.version
                current_game_state.versions.append(new_version)
                current_game_state.updated_at = datetime.utcnow()

                # Mark previous versions as not current
                for version in current_game_state.versions:
                    if version.version != new_version.version:
                        version.is_current = False

            modification_time = time.time() - start_time

            logger.info(
                "Game modification completed",
                session_id=request.session_id,
                code_changed=result["code_changed"],
                modification_time=modification_time,
            )

            return {
                **result,
                "modification_time": modification_time,
                "game_state": current_game_state,
                "modification_analysis": modification_analysis,
            }

        except Exception as e:
            logger.error("Game modification failed", session_id=request.session_id, error=str(e))
            raise ModificationError(f"Modification failed: {str(e)}")

    async def _apply_targeted_modification(
        self,
        request: GameModificationRequest,
        game_state: GameState,
        context: ConversationContext,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply targeted modifications for simple changes."""

        original_code = game_state.code
        modified_code = original_code
        modifications_applied = []

        try:
            # Handle color changes
            if "color" in request.message.lower():
                color_result = self._apply_color_changes(modified_code, request.message)
                if color_result["changed"]:
                    modified_code = color_result["code"]
                    modifications_applied.extend(color_result["changes"])

            # Handle size/dimension changes
            if any(
                word in request.message.lower()
                for word in ["size", "bigger", "smaller", "width", "height"]
            ):
                size_result = self._apply_size_changes(modified_code, request.message)
                if size_result["changed"]:
                    modified_code = size_result["code"]
                    modifications_applied.extend(size_result["changes"])

            # Handle speed changes
            if any(
                word in request.message.lower()
                for word in ["speed", "faster", "slower", "velocity"]
            ):
                speed_result = self._apply_speed_changes(modified_code, request.message)
                if speed_result["changed"]:
                    modified_code = speed_result["code"]
                    modifications_applied.extend(speed_result["changes"])

            # Validate modified code
            is_valid, issues = validator.validate_game_code(modified_code)
            if not is_valid:
                logger.warning("Modified code validation failed", issues=issues)
                # Fall back to AI modification
                return await self._apply_ai_modification(request, game_state, context)

            return {
                "modified_code": modified_code,
                "code_changed": modified_code != original_code,
                "modifications_applied": modifications_applied,
                "ai_response": self._generate_modification_response(modifications_applied),
                "strategy_used": "targeted_change",
                "validation_issues": issues if not is_valid else [],
            }

        except Exception as e:
            logger.error("Targeted modification failed", error=str(e))
            # Fall back to AI modification
            return await self._apply_ai_modification(request, game_state, context)

    async def _apply_ai_modification(
        self, request: GameModificationRequest, game_state: GameState, context: ConversationContext
    ) -> Dict[str, Any]:
        """Apply modifications using AI service."""

        try:
            # Use AI service to modify game
            ai_result = await self.ai_service.modify_game(request, game_state.code, context)

            return {
                "modified_code": ai_result["modified_code"],
                "code_changed": ai_result["code_changed"],
                "modifications_applied": ai_result["modifications_applied"],
                "ai_response": ai_result["ai_response"],
                "strategy_used": "ai_modification",
                "tokens_used": ai_result.get("tokens_used", 0),
                "validation_issues": ai_result.get("validation_issues", []),
            }

        except Exception as e:
            logger.error("AI modification failed", error=str(e))
            return await self._apply_fallback_modification(request, game_state, context)

    async def _apply_fallback_modification(
        self, request: GameModificationRequest, game_state: GameState, context: ConversationContext
    ) -> Dict[str, Any]:
        """Fallback modification strategy."""

        return {
            "modified_code": game_state.code,
            "code_changed": False,
            "modifications_applied": [],
            "ai_response": (
                "I couldn't apply the requested modification. "
                "Please try rephrasing your request."
            ),
            "strategy_used": "fallback",
            "error": "Modification could not be applied",
        }

    def _apply_color_changes(self, code: str, message: str) -> Dict[str, Any]:
        """Apply color changes to game code."""

        modified_code = code
        changes = []

        try:
            # Extract color information from message
            color_mapping = self._extract_color_changes(message)

            if color_mapping:
                # Apply color changes to JavaScript
                modified_code = self.js_parser.replace_color_values(modified_code, color_mapping)
                changes.append(f"Changed colors: {color_mapping}")

                return {"code": modified_code, "changed": True, "changes": changes}

        except Exception as e:
            logger.error("Color change failed", error=str(e))

        return {"code": code, "changed": False, "changes": []}

    def _apply_size_changes(self, code: str, message: str) -> Dict[str, Any]:
        """Apply size/dimension changes to game code."""

        # This would implement size change logic
        # For now, return unchanged
        return {"code": code, "changed": False, "changes": []}

    def _apply_speed_changes(self, code: str, message: str) -> Dict[str, Any]:
        """Apply speed/velocity changes to game code."""

        # This would implement speed change logic
        # For now, return unchanged
        return {"code": code, "changed": False, "changes": []}

    def _extract_color_changes(self, message: str) -> Dict[str, str]:
        """Extract color change requests from message."""

        color_mapping = {}
        message_lower = message.lower()

        # Simple color detection patterns
        color_names = {
            "red": "#ff0000",
            "blue": "#0000ff",
            "green": "#00ff00",
            "yellow": "#ffff00",
            "purple": "#800080",
            "orange": "#ffa500",
            "pink": "#ffc0cb",
            "black": "#000000",
            "white": "#ffffff",
        }

        # Look for patterns like "make X red" or "change Y to blue"
        for color_name, hex_value in color_names.items():
            if color_name in message_lower:
                # This is simplified - would need more sophisticated parsing
                color_mapping["#0066cc"] = hex_value  # Example mapping
                break

        return color_mapping

    def _analyze_modification_request(self, message: str, game_state: GameState) -> Dict[str, Any]:
        """Analyze modification request to determine strategy."""

        message_lower = message.lower()

        # Simple modification patterns
        simple_patterns = [
            "color",
            "size",
            "speed",
            "bigger",
            "smaller",
            "faster",
            "slower",
            "red",
            "blue",
            "green",
        ]

        complex_patterns = [
            "add",
            "remove",
            "create",
            "new",
            "feature",
            "level",
            "enemy",
            "sound",
            "physics",
        ]

        # Determine modification strategy
        simple_score = sum(1 for pattern in simple_patterns if pattern in message_lower)
        complex_score = sum(1 for pattern in complex_patterns if pattern in message_lower)

        if simple_score > complex_score and simple_score > 0:
            strategy = "targeted_change"
            confidence = simple_score / len(simple_patterns)
        else:
            strategy = "ai_regeneration"
            confidence = complex_score / len(complex_patterns) if complex_score > 0 else 0.5

        return {
            "strategy": strategy,
            "confidence": confidence,
            "simple_score": simple_score,
            "complex_score": complex_score,
            "estimated_complexity": "low" if simple_score > complex_score else "high",
        }

    async def _create_new_version(
        self,
        game_state: GameState,
        modification_result: Dict[str, Any],
        modification_summary: str,
    ) -> GameVersion:
        """Create new game version after modification."""

        new_version_number = game_state.current_version + 1

        return GameVersion(
            version=new_version_number,
            created_at=datetime.utcnow(),
            modification_summary=modification_summary[:200],
            modifications_applied=modification_result.get("modifications_applied", []),
            code_size=len(modification_result["modified_code"].encode("utf-8")),
            generation_time=modification_result.get("modification_time", 0),
            is_current=True,
            parent_version=game_state.current_version,
        )

    def _generate_modification_response(self, modifications: List[str]) -> str:
        """Generate AI response for successful modifications."""

        if not modifications:
            return "I've updated your game as requested!"

        if len(modifications) == 1:
            return f"I've applied the following change: {modifications[0]}"

        changes_text = ", ".join(modifications[:-1]) + f", and {modifications[-1]}"
        return f"I've applied the following changes: {changes_text}"

    def analyze_code_changes(self, original_code: str, modified_code: str) -> Dict[str, Any]:
        """Analyze differences between original and modified code."""

        if original_code == modified_code:
            return {"has_changes": False, "change_summary": "No changes"}

        # Calculate diff
        diff = list(
            difflib.unified_diff(
                original_code.splitlines(), modified_code.splitlines(), lineterm=""
            )
        )

        # Count changes
        additions = len([line for line in diff if line.startswith("+")])
        deletions = len([line for line in diff if line.startswith("-")])

        # Analyze change types
        change_types = []
        if any("color" in line.lower() for line in diff):
            change_types.append("color_change")
        if any("size" in line.lower() for line in diff):
            change_types.append("size_change")
        if any("speed" in line.lower() or "velocity" in line.lower() for line in diff):
            change_types.append("speed_change")

        return {
            "has_changes": True,
            "additions": additions,
            "deletions": deletions,
            "change_types": change_types,
            "diff_lines": len(diff),
            "change_summary": f"{additions} additions, {deletions} deletions",
        }

    async def revert_to_version(self, game_state: GameState, target_version: int) -> Dict[str, Any]:
        """Revert game to a previous version."""

        try:
            # Find target version
            target_version_obj = None
            for version in game_state.versions:
                if version.version == target_version:
                    target_version_obj = version
                    break

            if not target_version_obj:
                raise ModificationError(f"Version {target_version} not found")

            # This would require storing code for each version
            # For now, return error
            return {
                "success": False,
                "error": "Version revert not implemented - code storage needed",
            }

        except Exception as e:
            logger.error("Version revert failed", error=str(e))
            raise ModificationError(f"Revert failed: {str(e)}")
