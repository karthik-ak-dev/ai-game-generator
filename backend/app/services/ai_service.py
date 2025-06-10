"""
AI Service for OpenAI integration and game generation.
Production-ready service focused on core functionality.
"""

import hashlib
import re
import time
from typing import Any, Dict, Optional

import structlog
from openai import AsyncOpenAI

from ..config import settings
from ..models.game_models import GameGenerationRequest
from ..utils.constants import AI_PROMPTS
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class AIServiceError(Exception):
    """AI service specific errors."""

    pass


class AIService:
    """Production AI service for game generation."""

    def __init__(self):
        # OpenAI client with optimized settings
        self.client = AsyncOpenAI(
            api_key=settings.openai.api_key,
            timeout=settings.openai.timeout,
            max_retries=2,
        )

        # Performance tracking
        self._total_tokens_used = 0
        self._total_cost = 0.0
        self._request_count = 0

        # Response caching
        self._response_cache = {}
        self._cache_ttl = 1800  # 30 minutes

    async def generate_game(self, request: GameGenerationRequest) -> Dict[str, Any]:
        """
        Generate game from request.

        Args:
            request: Game generation request

        Returns:
            Dictionary with generated game code and metadata
        """
        start_time = time.time()

        try:
            # Basic validation
            if not request.prompt or len(request.prompt.strip()) < 10:
                raise AIServiceError("Prompt too short (minimum 10 characters)")

            if len(request.prompt) > 5000:
                raise AIServiceError("Prompt too long (maximum 5000 characters)")

            # Check cache
            cache_key = self._create_cache_key(
                "generate", request.prompt, request.game_type, request.engine
            )
            cached_result = await self._get_cached_response(cache_key)
            if cached_result:
                logger.info("Cache hit for game generation")
                return cached_result

            # Build prompt
            prompt = self._build_game_generation_prompt(request)

            # Call OpenAI
            response = await self._call_openai_api(prompt)

            # Extract game code
            game_code = self._extract_game_code(response["content"])

            # Basic validation
            if not self._validate_html_structure(game_code):
                raise AIServiceError("Generated code failed basic HTML validation")

            generation_time = time.time() - start_time

            result = {
                "game_code": game_code,
                "generation_time": generation_time,
                "tokens_used": response.get("tokens_used", 0),
                "metadata": {
                    "game_type": request.game_type or "arcade",
                    "engine": request.engine or "phaser",
                    "difficulty": request.difficulty or "beginner",
                },
            }

            # Cache result
            await self._cache_response(cache_key, result)

            logger.info(
                "Game generation completed",
                generation_time=generation_time,
                code_size=len(game_code),
                tokens_used=response.get("tokens_used", 0),
            )

            return result

        except Exception as e:
            logger.error("Game generation failed", error=str(e))
            raise AIServiceError(f"Generation failed: {str(e)}")

    # Private helper methods

    def _build_game_generation_prompt(self, request: GameGenerationRequest) -> str:
        """Build prompt for game generation."""
        game_type = request.game_type or self._detect_game_type(request.prompt)
        engine = request.engine or "phaser"

        context_parts = [
            AI_PROMPTS["system_base"],
            f"\nTASK: Generate a {game_type} game",
            f"ENGINE: {engine}",
            f"DIFFICULTY: {request.difficulty or 'beginner'}",
        ]

        if request.features:
            context_parts.append(f"FEATURES: {', '.join(request.features)}")

        main_prompt = AI_PROMPTS["game_creation"].format(
            game_type=game_type,
            description=request.prompt,
            engine=engine,
        )

        return "\n".join(context_parts) + "\n\n" + main_prompt

    def _detect_game_type(self, prompt: str) -> str:
        """Detect game type from prompt."""
        prompt_lower = prompt.lower()

        type_keywords = {
            "platformer": ["platform", "jump", "mario", "side-scroll"],
            "shooter": ["shoot", "gun", "bullet", "enemy", "space"],
            "puzzle": ["puzzle", "match", "tile", "brain", "logic"],
            "racing": ["race", "car", "speed", "track", "driving"],
        }

        for game_type, keywords in type_keywords.items():
            if any(keyword in prompt_lower for keyword in keywords):
                return game_type

        return "arcade"

    async def _call_openai_api(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API with error handling."""
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.openai.max_tokens,
                temperature=settings.openai.temperature,
            )

            self._request_count += 1
            tokens_used = response.usage.total_tokens if response.usage else 0
            self._total_tokens_used += tokens_used

            return {
                "content": response.choices[0].message.content,
                "tokens_used": tokens_used,
            }

        except Exception as e:
            logger.error("OpenAI API call failed", error=str(e))
            raise AIServiceError(f"AI API error: {str(e)}")

    def _extract_game_code(self, response_content: str) -> str:
        """Extract HTML game code from AI response."""
        # Look for HTML content between ```html and ``` or similar patterns
        html_patterns = [
            r"```html\n(.*?)\n```",
            r"```\n(<!DOCTYPE html.*?</html>)\n```",
            r"(<!DOCTYPE html.*?</html>)",
        ]

        for pattern in html_patterns:
            match = re.search(pattern, response_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no HTML found, return the entire response
        return response_content.strip()

    def _validate_html_structure(self, html_code: str) -> bool:
        """Basic HTML structure validation."""
        required_elements = [
            r"<!DOCTYPE\s+html>",
            r"<html[^>]*>",
            r"</html>",
            r"<head[^>]*>",
            r"<body[^>]*>",
        ]

        for pattern in required_elements:
            if not re.search(pattern, html_code, re.IGNORECASE):
                return False

        return True

    def _create_cache_key(self, operation: str, *args) -> str:
        """Create cache key for response caching."""
        key_data = f"{operation}:{''.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        try:
            cached_data = await redis_service.get(f"ai_cache:{cache_key}")
            if cached_data and isinstance(cached_data, dict):
                cache_time = cached_data.get("timestamp", 0)
                if time.time() - cache_time < self._cache_ttl:
                    return cached_data.get("data")
        except Exception:
            pass
        return None

    async def _cache_response(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Cache response with timestamp."""
        try:
            cache_data = {
                "data": response,
                "timestamp": time.time(),
            }
            await redis_service.set(f"ai_cache:{cache_key}", cache_data, ttl=self._cache_ttl)
        except Exception as e:
            logger.warning("Failed to cache response", error=str(e))
