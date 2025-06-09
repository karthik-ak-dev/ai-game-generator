"""
AI Service for OpenAI integration and prompt management.
Handles AI requests, prompt engineering, and response processing.
Production-optimized with connection pooling, caching, and circuit breakers.
"""

# Standard library imports
import asyncio
import hashlib
import re
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import aiohttp
import openai
import structlog
import tiktoken
from openai import AsyncOpenAI

from ..config import settings
from ..models.chat_models import ConversationContext
from ..models.game_models import GameGenerationRequest, GameModificationRequest
from ..utils.constants import AI_PROMPTS, OPENAI_MODELS
from ..utils.validation import validator
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class AIServiceError(Exception):
    """AI service specific errors."""

    pass


class TokenManager:
    """Production-optimized token counting and management."""

    def __init__(self, model: str = "gpt-4-1106-preview"):
        self.model = model
        self._encoding_cache = {}
        self._token_cache = {}

    @lru_cache(maxsize=10)
    def get_encoding(self, model: str):
        """Get encoding with caching to avoid repeated initialization."""
        try:
            return tiktoken.encoding_for_model(model)
        except Exception:
            # Fallback to cl100k_base for unknown models
            return tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens with caching for repeated text."""
        # Use hash for cache key to handle large text efficiently
        text_hash = hashlib.md5(text.encode()).hexdigest()

        if text_hash in self._token_cache:
            return self._token_cache[text_hash]

        encoding = self.get_encoding(self.model)
        token_count = len(encoding.encode(text))

        # Cache only if text is not too large
        if len(text) < 10000:
            self._token_cache[text_hash] = token_count

        return token_count

    def truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Optimized token truncation."""
        if self.count_tokens(text) <= max_tokens:
            return text

        encoding = self.get_encoding(self.model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost with updated pricing."""
        model_config = OPENAI_MODELS.get(self.model, {})
        input_cost = model_config.get("input_cost_per_1k", 0.01)
        output_cost = model_config.get("output_cost_per_1k", 0.03)

        return (input_tokens / 1000 * input_cost) + (output_tokens / 1000 * output_cost)

    def clear_cache(self):
        """Clear token cache to prevent memory growth."""
        if len(self._token_cache) > 1000:
            # Keep only most recent 500 entries
            items = list(self._token_cache.items())
            self._token_cache = dict(items[-500:])


class PromptEngine:
    """Production-optimized prompt engineering with caching."""

    def __init__(self):
        self.token_manager = TokenManager(settings.openai.model)
        self._prompt_cache = {}

    def build_game_generation_prompt(self, request: GameGenerationRequest) -> str:
        """
        Build optimized prompt for game generation with caching.

        Args:
            request: Game generation request

        Returns:
            Optimized prompt string
        """
        # Create cache key from request parameters
        cache_key = self._create_prompt_cache_key(request)

        if cache_key in self._prompt_cache:
            cached_prompt = self._prompt_cache[cache_key]
            # Replace only the dynamic description part
            return cached_prompt.replace("{{DESCRIPTION}}", request.prompt)

        # Build prompt components
        engine = request.engine or "phaser"
        game_type = request.game_type or self._detect_game_type(request.prompt)

        context_parts = [
            AI_PROMPTS["system_base"],
            f"\nCURRENT TASK: Generate a {game_type} game",
            f"TARGET ENGINE: {engine}",
            f"DIFFICULTY LEVEL: {request.difficulty}",
        ]

        if request.features:
            context_parts.append(f"REQUIRED FEATURES: {', '.join(request.features)}")

        # Add optimized game-specific guidance
        game_guidance = self._get_game_type_guidance(game_type, engine)
        if game_guidance:
            context_parts.append(f"\nGAME TYPE GUIDANCE:\n{game_guidance}")

        # Build main prompt with placeholder
        main_prompt = AI_PROMPTS["game_creation"].format(
            game_type=game_type,
            description="{{DESCRIPTION}}",  # Placeholder for caching
            engine=engine,
        )

        full_prompt = "\n".join(context_parts) + "\n\n" + main_prompt

        # Cache the prompt template
        self._prompt_cache[cache_key] = full_prompt

        # Replace placeholder with actual description
        final_prompt = full_prompt.replace("{{DESCRIPTION}}", request.prompt)

        # Optimize for token limit
        max_prompt_tokens = settings.openai.max_tokens // 2
        return self.token_manager.truncate_to_token_limit(final_prompt, max_prompt_tokens)

    def build_modification_prompt(
        self,
        request: GameModificationRequest,
        current_code: str,
        conversation_context: ConversationContext,
    ) -> str:
        """
        Build optimized prompt for game modification.

        Args:
            request: Modification request
            current_code: Current game code
            conversation_context: Conversation history

        Returns:
            Optimized prompt string
        """
        # Build conversation history efficiently
        history_parts = []
        recent_messages = conversation_context.conversation_history[-8:]  # Reduced from 10

        for message in recent_messages:
            role = "User" if message.role == "user" else "Assistant"
            # Truncate very long messages
            content = message.content
            if len(content) > 200:
                content = content[:200] + "..."
            history_parts.append(f"{role}: {content}")

        conversation_history = "\n".join(history_parts)

        # Detect modification intent with caching
        modification_intent = self._analyze_modification_intent(request.message)

        # Build context
        context_parts = [
            AI_PROMPTS["system_base"],
            f"\nMODIFICATION TASK: {modification_intent['type']}",
            f"CONFIDENCE: {modification_intent['confidence']:.2f}",
        ]

        if request.preserve_features:
            context_parts.append(f"PRESERVE FEATURES: {', '.join(request.preserve_features)}")

        # Add modification-specific guidance
        mod_guidance = self._get_modification_guidance(modification_intent["type"])
        if mod_guidance:
            context_parts.append(f"\nMODIFICATION GUIDANCE:\n{mod_guidance}")

        # Optimize code size for prompt
        optimized_code = self._optimize_code_for_prompt(current_code)

        # Build main prompt
        main_prompt = AI_PROMPTS["game_modification"].format(
            modification_request=request.message,
            current_code=optimized_code,
            conversation_history=conversation_history,
        )

        full_prompt = "\n".join(context_parts) + "\n\n" + main_prompt

        # Optimize for token limit
        max_prompt_tokens = settings.openai.max_tokens // 2
        return self.token_manager.truncate_to_token_limit(full_prompt, max_prompt_tokens)

    def _create_prompt_cache_key(self, request: GameGenerationRequest) -> str:
        """Create cache key for prompt caching."""
        key_parts = [
            request.game_type or "auto",
            request.engine or "phaser",
            request.difficulty or "beginner",
            "_".join(sorted(request.features or [])),
        ]
        return "|".join(key_parts)

    def _optimize_code_for_prompt(self, code: str) -> str:
        """Optimize code size for inclusion in prompts."""
        # Remove comments and extra whitespace
        lines = code.split("\n")
        optimized_lines = []

        for line in lines:
            # Remove HTML comments
            line = re.sub(r"<!--.*?-->", "", line)
            # Remove JS comments
            line = re.sub(r"//.*$", "", line)
            # Strip whitespace
            line = line.strip()
            if line:
                optimized_lines.append(line)

        optimized_code = "\n".join(optimized_lines)

        # If still too large, truncate intelligently
        if len(optimized_code) > 8000:
            # Keep essential parts: DOCTYPE, head, and beginning of body
            parts = optimized_code.split("<body")
            if len(parts) >= 2:
                head_part = parts[0] + "<body"
                body_part = parts[1]

                # Take first part of body
                if len(body_part) > 4000:
                    body_part = (
                        body_part[:4000]
                        + "\n<!-- ... rest of code truncated ... -->\n</body>\n</html>"
                    )

                optimized_code = head_part + body_part

        return optimized_code

    @lru_cache(maxsize=100)
    def _detect_game_type(self, prompt: str) -> str:
        """Cached game type detection."""
        prompt_lower = prompt.lower()

        type_keywords = {
            "platformer": ["platform", "jump", "mario", "side-scroll", "gravity"],
            "shooter": ["shoot", "gun", "bullet", "enemy", "space", "fire"],
            "puzzle": ["puzzle", "match", "tile", "brain", "logic", "solve"],
            "racing": ["race", "car", "speed", "track", "driving", "lap"],
            "arcade": ["arcade", "classic", "retro", "simple", "score"],
        }

        scores = {}
        for game_type, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in prompt_lower)
            scores[game_type] = score

        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else "arcade"

    @lru_cache(maxsize=50)
    def _get_game_type_guidance(self, game_type: str, engine: str) -> str:
        """Cached game type guidance."""
        guidance_map = {
            "platformer": {
                "phaser": "Use Phaser 3 physics, implement player controls, create platforms, add jumping mechanics",
                "three": "Use Three.js for 2.5D/3D platformer, implement character controller with physics",
            },
            "shooter": {
                "phaser": "Create player ship, implement bullet system, add enemy spawning and collision detection"
            },
            "puzzle": {
                "phaser": "Create grid-based gameplay, implement matching logic, add scoring system"
            },
        }

        return guidance_map.get(game_type, {}).get(engine, "")

    @lru_cache(maxsize=50)
    def _analyze_modification_intent(self, message: str) -> Dict[str, Any]:
        """Cached modification intent analysis."""
        message_lower = message.lower()

        intent_patterns = {
            "visual_change": ["color", "size", "appearance", "look", "visual", "style"],
            "gameplay_change": ["speed", "difficulty", "controls", "physics", "mechanics"],
            "feature_addition": ["add", "include", "new", "create", "implement"],
            "bug_fix": ["fix", "broken", "error", "not working", "issue", "problem"],
            "content_addition": ["more", "level", "enemy", "power", "item", "sound"],
        }

        scores = {}
        for intent_type, patterns in intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in message_lower)
            scores[intent_type] = score / len(patterns) if patterns else 0

        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]

        return {"type": best_intent, "confidence": confidence, "all_scores": scores}

    @lru_cache(maxsize=20)
    def _get_modification_guidance(self, modification_type: str) -> str:
        """Cached modification guidance."""
        guidance_map = {
            "visual_change": "Make targeted visual changes while preserving functionality. Update CSS or JavaScript variables safely.",
            "gameplay_change": "Modify game parameters carefully. Adjust physics, speeds, or difficulty while maintaining balance.",
            "feature_addition": "Add new features without breaking existing ones. Integrate smoothly with existing code patterns.",
            "bug_fix": "Identify and fix the specific issue. Make minimal changes to resolve the problem.",
        }

        return guidance_map.get(modification_type, "")


class CircuitBreaker:
    """Circuit breaker for AI service operations."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == "OPEN":
                if (
                    datetime.utcnow() - self.last_failure_time
                ).total_seconds() > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                else:
                    raise AIServiceError("AI service circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                await self._on_success()
                return result
            except Exception as e:
                await self._on_failure()
                raise e

    async def _on_success(self):
        """Reset circuit breaker on successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    async def _on_failure(self):
        """Handle failure in circuit breaker."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class AIService:
    """Production-optimized AI service with connection pooling and caching."""

    def __init__(self):
        # Connection with optimized settings
        connector = aiohttp.TCPConnector(
            limit=20,  # Max connections
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
        )

        self.client = AsyncOpenAI(
            api_key=settings.openai.api_key,
            timeout=settings.openai.timeout,
            max_retries=0,  # We handle retries manually
            http_client=aiohttp.ClientSession(connector=connector),
        )

        self.prompt_engine = PromptEngine()
        self.token_manager = TokenManager(settings.openai.model)
        self.circuit_breaker = CircuitBreaker()

        # Performance tracking
        self._call_count = 0
        self._total_tokens_used = 0
        self._total_cost = 0.0
        self._cache_hits = 0

        # Request rate limiting
        self._request_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests

        # Response caching
        self._response_cache = {}
        self._cache_ttl = 1800  # 30 minutes

    async def generate_game(self, request: GameGenerationRequest) -> Dict[str, Any]:
        """
        Production-optimized game generation with caching and rate limiting.

        Args:
            request: Game generation request

        Returns:
            Dictionary containing generated game and metadata
        """
        start_time = time.time()

        # Check cache first
        cache_key = self._create_cache_key(
            "generate", request.prompt, request.game_type, request.engine
        )
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            self._cache_hits += 1
            logger.info("Cache hit for game generation", cache_key=cache_key[:20])
            return cached_result

        async with self._request_semaphore:
            try:
                # Rate limiting
                await self._enforce_rate_limit()

                # Validate request
                is_valid, issues = validator.validate_game_generation_request(request.prompt)
                if not is_valid:
                    raise AIServiceError(f"Invalid request: {', '.join(issues)}")

                # Build optimized prompt
                prompt = self.prompt_engine.build_game_generation_prompt(request)

                logger.info(
                    "Generating game",
                    game_type=request.game_type,
                    engine=request.engine,
                    prompt_length=len(prompt),
                    tokens=self.token_manager.count_tokens(prompt),
                )

                # Call OpenAI API with circuit breaker
                response = await self.circuit_breaker.call(self._call_openai_api, prompt)

                # Process response
                game_code = await self._extract_game_code_async(response["content"])

                # Validate generated code asynchronously
                validation_task = asyncio.create_task(self._validate_code_async(game_code))

                try:
                    code_valid, code_issues = await asyncio.wait_for(validation_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Code validation timed out, proceeding with unvalidated code")
                    code_valid, code_issues = True, []

                if not code_valid and code_issues:
                    # Attempt quick fixes
                    game_code = await self._attempt_code_fix_async(game_code, code_issues)

                generation_time = time.time() - start_time

                # Calculate costs
                estimated_cost = self.token_manager.estimate_cost(
                    response.get("prompt_tokens", 0), response.get("completion_tokens", 0)
                )

                result = {
                    "game_code": game_code,
                    "generation_time": generation_time,
                    "tokens_used": response.get("tokens_used", 0),
                    "model_used": settings.openai.model,
                    "prompt_tokens": response.get("prompt_tokens", 0),
                    "completion_tokens": response.get("completion_tokens", 0),
                    "estimated_cost": estimated_cost,
                    "validation_issues": code_issues if not code_valid else [],
                    "cache_hit": False,
                    "metadata": {
                        "game_type": request.game_type
                        or self.prompt_engine._detect_game_type(request.prompt),
                        "engine": request.engine,
                        "difficulty": request.difficulty,
                        "features_requested": request.features or [],
                    },
                }

                # Update metrics
                self._call_count += 1
                self._total_tokens_used += response.get("tokens_used", 0)
                self._total_cost += estimated_cost

                # Cache successful result
                await self._cache_response(cache_key, result)

                logger.info(
                    "Game generation completed",
                    generation_time=generation_time,
                    tokens_used=response.get("tokens_used", 0),
                    code_length=len(game_code),
                    estimated_cost=estimated_cost,
                )

                return result

            except Exception as e:
                logger.error("Game generation failed", error=str(e))
                raise AIServiceError(f"Failed to generate game: {str(e)}")

    async def modify_game(
        self,
        request: GameModificationRequest,
        current_code: str,
        conversation_context: ConversationContext,
    ) -> Dict[str, Any]:
        """
        Production-optimized game modification with caching.

        Args:
            request: Modification request
            current_code: Current game code
            conversation_context: Conversation history

        Returns:
            Dictionary containing modified game and metadata
        """
        start_time = time.time()

        # Create cache key including code hash
        code_hash = hashlib.md5(current_code.encode()).hexdigest()[:16]
        cache_key = self._create_cache_key("modify", request.message, code_hash)

        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            self._cache_hits += 1
            logger.info("Cache hit for game modification", cache_key=cache_key[:20])
            return cached_result

        async with self._request_semaphore:
            try:
                # Rate limiting
                await self._enforce_rate_limit()

                # Validate request
                is_valid, issues = validator.validate_chat_request(
                    request.message, request.session_id
                )
                if not is_valid:
                    raise AIServiceError(f"Invalid modification request: {', '.join(issues)}")

                # Build modification prompt
                prompt = self.prompt_engine.build_modification_prompt(
                    request, current_code, conversation_context
                )

                logger.info(
                    "Modifying game",
                    session_id=request.session_id,
                    modification_type=request.modification_type,
                    prompt_length=len(prompt),
                )

                # Call OpenAI API with circuit breaker
                response = await self.circuit_breaker.call(self._call_openai_api, prompt)

                # Process response
                modified_code = await self._extract_game_code_async(response["content"])
                ai_response = self._extract_ai_response(response["content"])

                # Validate modified code with timeout
                validation_task = asyncio.create_task(self._validate_code_async(modified_code))

                try:
                    code_valid, code_issues = await asyncio.wait_for(validation_task, timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Modification validation timed out")
                    code_valid, code_issues = True, []

                if not code_valid and code_issues:
                    modified_code = await self._attempt_code_fix_async(modified_code, code_issues)

                # Analyze modifications efficiently
                modifications_applied = self._analyze_code_changes_fast(current_code, modified_code)

                modification_time = time.time() - start_time
                estimated_cost = self.token_manager.estimate_cost(
                    response.get("prompt_tokens", 0), response.get("completion_tokens", 0)
                )

                result = {
                    "modified_code": modified_code,
                    "ai_response": ai_response,
                    "modifications_applied": modifications_applied,
                    "modification_time": modification_time,
                    "tokens_used": response.get("tokens_used", 0),
                    "model_used": settings.openai.model,
                    "estimated_cost": estimated_cost,
                    "validation_issues": code_issues if not code_valid else [],
                    "code_changed": current_code != modified_code,
                    "cache_hit": False,
                }

                # Update metrics
                self._call_count += 1
                self._total_tokens_used += response.get("tokens_used", 0)
                self._total_cost += estimated_cost

                # Cache result
                await self._cache_response(cache_key, result)

                logger.info(
                    "Game modification completed",
                    modification_time=modification_time,
                    tokens_used=response.get("tokens_used", 0),
                    code_changed=result["code_changed"],
                )

                return result

            except Exception as e:
                logger.error("Game modification failed", error=str(e))
                raise AIServiceError(f"Failed to modify game: {str(e)}")

    async def _call_openai_api(self, prompt: str) -> Dict[str, Any]:
        """
        Optimized OpenAI API call with retry logic and timeout handling.
        """
        max_retries = 2  # Reduced from 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                # Count input tokens
                prompt_tokens = self.token_manager.count_tokens(prompt)

                # Prepare request with optimized parameters
                request_params = {
                    "model": settings.openai.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": min(
                        settings.openai.max_tokens, 4000
                    ),  # Optimize for faster responses
                    "temperature": settings.openai.temperature,
                    "timeout": min(settings.openai.timeout, 30),  # Reduced timeout
                }

                # Make API call with timeout
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(**request_params),
                    timeout=35,  # Slightly higher than request timeout
                )

                # Extract response data
                content = response.choices[0].message.content
                completion_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens

                return {
                    "content": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "tokens_used": total_tokens,
                    "model": settings.openai.model,
                    "attempt": attempt + 1,
                }

            except openai.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        f"Rate limit hit, waiting {wait_time}s, attempt {attempt + 1}/{max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise AIServiceError(f"Rate limit exceeded after {max_retries} attempts")

            except (openai.APITimeoutError, asyncio.TimeoutError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"API timeout, attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(retry_delay)
                    continue
                raise AIServiceError(f"API timeout after {max_retries} attempts")

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.error(f"OpenAI API error: {str(e)}, attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(retry_delay)
                    continue
                raise AIServiceError(f"API call failed: {str(e)}")

        raise AIServiceError("Max retries exceeded")

    async def _extract_game_code_async(self, response_content: str) -> str:
        """Extract HTML game code asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_game_code_sync, response_content)

    def _extract_game_code_sync(self, response_content: str) -> str:
        """Synchronous game code extraction."""
        # Optimized HTML extraction patterns
        html_patterns = [
            r"```html\n(.*?)\n```",
            r"```\n(<!DOCTYPE html.*?)</html>",
            r"(<!DOCTYPE html.*?</html>)",
        ]

        for pattern in html_patterns:
            match = re.search(pattern, response_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no code block found but contains DOCTYPE
        if "<!DOCTYPE html" in response_content:
            return response_content.strip()

        raise AIServiceError("No valid HTML code found in AI response")

    async def _validate_code_async(self, code: str) -> Tuple[bool, List[str]]:
        """Validate code asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, validator.validate_game_code, code)

    async def _attempt_code_fix_async(self, game_code: str, issues: List[str]) -> str:
        """Attempt to fix code issues asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fix_code_sync, game_code, issues)

    def _fix_code_sync(self, game_code: str, issues: List[str]) -> str:
        """Synchronous code fixing."""
        fixed_code = game_code

        # Quick fixes for common issues
        for issue in issues:
            if "DOCTYPE" in issue and "<!DOCTYPE html>" not in fixed_code:
                fixed_code = "<!DOCTYPE html>\n" + fixed_code

            if "closing tag" in issue and not fixed_code.strip().endswith("</html>"):
                fixed_code = fixed_code.rstrip() + "\n</html>"

        return fixed_code

    def _analyze_code_changes_fast(self, original_code: str, modified_code: str) -> List[str]:
        """Fast code change analysis."""
        changes = []

        if original_code == modified_code:
            return ["no_changes"]

        changes.append("code_modified")

        # Quick checks for common changes
        if len(modified_code) != len(original_code):
            changes.append("size_changed")

        # Check for color changes (hex patterns)
        orig_colors = set(re.findall(r"#[0-9a-fA-F]{6}", original_code))
        mod_colors = set(re.findall(r"#[0-9a-fA-F]{6}", modified_code))
        if orig_colors != mod_colors:
            changes.append("colors_modified")

        return changes

    # Caching methods

    def _create_cache_key(self, operation: str, *args) -> str:
        """Create cache key from operation and arguments."""
        key_data = f"{operation}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response from Redis."""
        try:
            cached_data = await redis_service.get(f"ai_cache:{cache_key}")
            if cached_data and isinstance(cached_data, dict):
                # Check if cache is still valid
                cache_time = cached_data.get("cached_at", 0)
                if time.time() - cache_time < self._cache_ttl:
                    cached_data["cache_hit"] = True
                    return cached_data
                else:
                    # Remove expired cache
                    await redis_service.delete(f"ai_cache:{cache_key}")
        except Exception as e:
            logger.warning("Failed to get cached response", error=str(e))

        return None

    async def _cache_response(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Cache response in Redis."""
        try:
            # Add cache metadata
            cache_data = {**response, "cached_at": time.time(), "cache_key": cache_key}

            # Store with TTL
            await redis_service.set(f"ai_cache:{cache_key}", cache_data, ttl=self._cache_ttl)
        except Exception as e:
            logger.warning("Failed to cache response", error=str(e))

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive AI service statistics."""
        return {
            "total_calls": self._call_count,
            "total_tokens_used": self._total_tokens_used,
            "total_cost": round(self._total_cost, 4),
            "average_tokens_per_call": self._total_tokens_used / max(self._call_count, 1),
            "average_cost_per_call": self._total_cost / max(self._call_count, 1),
            "cache_hits": self._cache_hits,
            "cache_hit_rate": (self._cache_hits / max(self._call_count, 1)) * 100,
            "model_used": settings.openai.model,
            "circuit_breaker_state": self.circuit_breaker.state,
        }

    async def cleanup_resources(self):
        """Clean up resources for graceful shutdown."""
        try:
            # Clear caches
            self.prompt_engine._prompt_cache.clear()
            self.token_manager.clear_cache()
            self._response_cache.clear()

            # Close HTTP client
            if hasattr(self.client, "_client") and hasattr(self.client._client, "close"):
                await self.client._client.close()

            logger.info("AI service resources cleaned up")
        except Exception as e:
            logger.error("Failed to cleanup AI service resources", error=str(e))
