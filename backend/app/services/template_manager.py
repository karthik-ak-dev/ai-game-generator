"""
Template manager for handling game templates and template operations.
Manages template loading, validation, instantiation, and CRUD operations.
Production-optimized with Redis persistence and LRU caching.
"""

# Standard library imports
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
import structlog

# Local application imports
from ..models.game_models import GameState, GameTemplate
from ..models.template_models import (
    TemplateAnalytics,
    TemplateCategory,
    TemplateSearchRequest,
    TemplateSearchResult,
)
from ..utils.code_utils import CodeAnalyzer, HTMLParser
from ..utils.constants import DIFFICULTY_LEVELS, GAME_ENGINES, GameType
from ..utils.validation import validator
from .redis_service import redis_service

logger = structlog.get_logger(__name__)


class TemplateError(Exception):
    """Template management specific errors."""

    pass


class LRUCache:
    """Thread-safe LRU cache with TTL support for production use."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self.cache:
                return None

            # Check TTL
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            # Remove oldest items if at capacity
            while len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]

            self.cache[key] = value
            self.timestamps[key] = time.time()

    async def delete(self, key: str) -> None:
        async with self._lock:
            self.cache.pop(key, None)
            self.timestamps.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self.cache.clear()
            self.timestamps.clear()


class TemplateManager:
    """Production-optimized template manager with Redis persistence and caching."""

    def __init__(self):
        # Use Redis for persistence instead of in-memory storage
        self.template_cache = LRUCache(max_size=500, ttl=1800)  # 30 min TTL
        self.usage_cache = LRUCache(max_size=1000, ttl=900)  # 15 min TTL

        # Lightweight utilities
        self.html_parser = HTMLParser()
        self.code_analyzer = CodeAnalyzer()

        # Rate limiting for template operations
        self._operation_semaphore = asyncio.Semaphore(50)  # Max 50 concurrent operations

        # Circuit breaker state
        self._circuit_breaker = {
            "failures": 0,
            "last_failure": None,
            "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
        }

        # Load default templates asynchronously
        asyncio.create_task(self._load_default_templates_async())

    async def get_template(self, template_id: str) -> Optional[GameTemplate]:
        """
        Get template by ID with caching and circuit breaker.

        Args:
            template_id: Template identifier

        Returns:
            GameTemplate object or None if not found
        """
        if not template_id or len(template_id) > 100:
            return None

        async with self._operation_semaphore:
            try:
                # Check cache first
                cached_template = await self.template_cache.get(template_id)
                if cached_template:
                    # Update usage stats asynchronously
                    asyncio.create_task(self._increment_usage_count_async(template_id))
                    return cached_template

                # Check circuit breaker
                if not await self._circuit_breaker_check():
                    logger.warning("Circuit breaker open, using fallback", template_id=template_id)
                    return None

                # Load from Redis
                template_data = await redis_service.get(f"template:{template_id}")
                if template_data:
                    try:
                        template = GameTemplate.parse_obj(template_data)
                        # Cache for future use
                        await self.template_cache.set(template_id, template)

                        # Update usage stats asynchronously
                        asyncio.create_task(self._increment_usage_count_async(template_id))

                        await self._circuit_breaker_success()
                        return template
                    except Exception as e:
                        logger.error(
                            "Failed to parse template data", template_id=template_id, error=str(e)
                        )
                        await self._circuit_breaker_failure()
                        return None

                await self._circuit_breaker_success()
                return None

            except Exception as e:
                logger.error("Failed to get template", template_id=template_id, error=str(e))
                await self._circuit_breaker_failure()
                return None

    async def create_template(self, request: TemplateCreationRequest) -> GameTemplate:
        """
        Create a new template with validation and persistence.

        Args:
            request: Template creation request

        Returns:
            Created GameTemplate object
        """
        async with self._operation_semaphore:
            try:
                # Input validation
                if not request.metadata or not request.metadata.name:
                    raise TemplateError("Template name is required")

                if len(request.code_template) > 500_000:  # 500KB limit
                    raise TemplateError("Template code too large (max 500KB)")

                # Validate template asynchronously
                validation_result = await self._validate_template_async(
                    request.code_template, request.variables
                )

                if not validation_result.is_valid:
                    raise TemplateError(f"Template validation failed: {validation_result.errors}")

                # Generate template ID
                template_id = await self._generate_template_id_async(request.metadata.name)

                # Create template object
                template = GameTemplate(
                    id=template_id,
                    metadata=request.metadata,
                    code_template=request.code_template,
                    variables=request.variables,
                    preview_code=request.preview_code,
                    instructions=request.instructions,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    usage_count=0,
                    is_active=True,
                )

                # Store in Redis with TTL
                template_data = template.dict()
                await redis_service.set(
                    f"template:{template_id}", template_data, ttl=86400
                )  # 24h TTL

                # Cache locally
                await self.template_cache.set(template_id, template)

                # Initialize usage stats asynchronously
                asyncio.create_task(self._initialize_usage_stats_async(template_id))

                logger.info("Template created", template_id=template_id, name=request.metadata.name)

                return template

            except Exception as e:
                logger.error("Failed to create template", error=str(e))
                raise TemplateError(f"Template creation failed: {str(e)}")

    async def update_template(
        self, template_id: str, request: TemplateUpdateRequest
    ) -> Optional[GameTemplate]:
        """
        Update an existing template.

        Args:
            template_id: Template identifier
            request: Template update request

        Returns:
            Updated GameTemplate object or None if not found
        """
        try:
            template = await self.get_template(template_id)
            if not template:
                return None

            # Apply updates
            if request.metadata:
                template.metadata = request.metadata

            if request.code_template:
                # Validate new code
                validation_result = await self.validate_template(
                    request.code_template, request.variables or template.variables
                )

                if not validation_result.is_valid:
                    raise TemplateError(f"Template validation failed: {validation_result.errors}")

                template.code_template = request.code_template

            if request.variables:
                template.variables = request.variables

            if request.preview_code:
                template.preview_code = request.preview_code

            if request.instructions:
                template.instructions = request.instructions

            if request.is_active is not None:
                template.is_active = request.is_active

            template.updated_at = datetime.utcnow()

            # Store updated template
            await redis_service.set(f"template:{template_id}", template.dict(), ttl=86400)

            logger.info("Template updated", template_id=template_id)

            return template

        except Exception as e:
            logger.error("Failed to update template", template_id=template_id, error=str(e))
            raise TemplateError(f"Template update failed: {str(e)}")

    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.

        Args:
            template_id: Template identifier

        Returns:
            True if successful, False if not found
        """
        try:
            if await redis_service.exists(f"template:{template_id}"):
                await redis_service.delete(f"template:{template_id}")

                # Also remove usage stats
                await redis_service.delete(f"template_usage:{template_id}")

                logger.info("Template deleted", template_id=template_id)
                return True

            return False

        except Exception as e:
            logger.error("Failed to delete template", template_id=template_id, error=str(e))
            return False

    async def search_templates(self, request: TemplateSearchRequest) -> TemplateSearchResult:
        """
        Search templates with pagination and performance optimization.

        Args:
            request: Search request

        Returns:
            TemplateSearchResult with matching templates
        """
        try:
            # Validate pagination parameters
            page = max(1, request.page or 1)
            page_size = min(100, max(1, request.page_size or 20))  # Limit page size

            # Create cache key for search
            cache_key = f"search:{hash(str(request.dict()))}"

            # Check cache first
            cached_result = await self.template_cache.get(cache_key)
            if cached_result:
                return cached_result

            # Get template IDs from Redis (streaming approach)
            pattern = "template:*"
            template_ids = await redis_service.client.keys(pattern)

            # Limit number of templates to process for performance
            if len(template_ids) > 1000:
                template_ids = template_ids[:1000]
                logger.warning("Large template search limited to 1000 results")

            # Load templates in batches to avoid memory issues
            batch_size = 50
            filtered_templates = []

            for i in range(0, len(template_ids), batch_size):
                batch_ids = template_ids[i : i + batch_size]
                batch_templates = await self._load_template_batch(batch_ids, request)
                filtered_templates.extend(batch_templates)

                # Yield control to prevent blocking
                if i % 100 == 0:
                    await asyncio.sleep(0.001)

            # Sort efficiently
            filtered_templates = await self._sort_templates_async(filtered_templates, request)

            # Apply pagination
            total_count = len(filtered_templates)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_templates = filtered_templates[start_idx:end_idx]

            result = TemplateSearchResult(
                templates=page_templates,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_more=end_idx < total_count,
            )

            # Cache result for 5 minutes
            await self.template_cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error("Template search failed", error=str(e))
            return TemplateSearchResult(
                templates=[], total_count=0, page=page, page_size=page_size, has_more=False
            )

    async def instantiate_template(self, request: TemplateInstantiation) -> Dict[str, Any]:
        """
        Instantiate a template with performance optimization.

        Args:
            request: Template instantiation request

        Returns:
            Dictionary with instantiated code and metadata
        """
        async with self._operation_semaphore:
            try:
                template = await self.get_template(request.template_id)
                if not template:
                    raise TemplateError(f"Template {request.template_id} not found")

                # Use compiled regex for better performance
                instantiated_code = await self._instantiate_code_async(
                    template.code_template, template.variables, request.variable_values
                )

                # Validate asynchronously with timeout
                validation_task = asyncio.create_task(
                    self._validate_instantiated_code_async(instantiated_code)
                )

                try:
                    is_valid, issues = await asyncio.wait_for(validation_task, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("Template validation timed out", template_id=request.template_id)
                    is_valid, issues = False, ["Validation timeout"]

                # Track usage asynchronously
                asyncio.create_task(self._track_template_usage_async(request.template_id, is_valid))

                return {
                    "code": instantiated_code,
                    "template_id": request.template_id,
                    "template_name": template.metadata.name,
                    "variables_used": request.variable_values,
                    "validation_issues": issues,
                    "is_valid": is_valid,
                }

            except Exception as e:
                logger.error(
                    "Template instantiation failed", template_id=request.template_id, error=str(e)
                )

                # Track failed usage
                asyncio.create_task(self._track_template_usage_async(request.template_id, False))

                raise TemplateError(f"Template instantiation failed: {str(e)}")

    async def validate_template(
        self, code_template: str, variables: List[Any]
    ) -> TemplateValidationResult:
        """
        Validate a template.

        Args:
            code_template: Template code to validate
            variables: Template variables

        Returns:
            TemplateValidationResult
        """
        try:
            errors = []
            warnings = []
            missing_variables = []
            unused_variables = []

            # Basic code validation
            is_valid, code_issues = validator.validate_game_code(code_template)
            if not is_valid:
                errors.extend(code_issues)

            # Check for variable placeholders
            variable_names = {var.name for var in variables}

            # Find variables used in template
            import re

            used_variables = set(re.findall(r"\{\{(\w+)\}\}", code_template))

            # Check for missing variable definitions
            for used_var in used_variables:
                if used_var not in variable_names:
                    missing_variables.append(used_var)

            # Check for unused variable definitions
            for var_name in variable_names:
                if var_name not in used_variables:
                    unused_variables.append(var_name)

            # Analyze code metrics
            code_metrics = self.code_analyzer.analyze_complexity(code_template, "html")

            # Add warnings for large templates
            if code_metrics.get("size_bytes", 0) > 100000:  # 100KB
                warnings.append("Template is quite large")

            if code_metrics.get("complexity_score", 0) > 50:
                warnings.append("Template has high complexity")

            final_is_valid = len(errors) == 0 and len(missing_variables) == 0

            return TemplateValidationResult(
                is_valid=final_is_valid,
                errors=errors,
                warnings=warnings,
                missing_variables=missing_variables,
                unused_variables=unused_variables,
                code_metrics=code_metrics,
            )

        except Exception as e:
            logger.error("Template validation failed", error=str(e))
            return TemplateValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=[],
                missing_variables=[],
                unused_variables=[],
                code_metrics={},
            )

    async def get_template_usage_stats(self, template_id: str) -> Optional[TemplateUsageStats]:
        """Get usage statistics for a template."""
        return await redis_service.get(f"template_stats:{template_id}")

    async def rate_template(self, rating: TemplateRating) -> bool:
        """
        Rate a template.

        Args:
            rating: Template rating

        Returns:
            True if successful, False otherwise
        """
        try:
            template = await self.get_template(rating.template_id)
            if not template:
                return False

            # Update template rating
            # In a full implementation, would store individual ratings and calculate average
            # For now, just update the template rating directly
            template.rating = (template.rating or 0 + rating.rating) / 2  # Simplified

            logger.info("Template rated", template_id=rating.template_id, rating=rating.rating)

            return True

        except Exception as e:
            logger.error("Failed to rate template", template_id=rating.template_id, error=str(e))
            return False

    # Async helper methods for better performance

    async def _load_template_batch(
        self, template_ids: List[str], request: TemplateSearchRequest
    ) -> List[GameTemplate]:
        """Load and filter a batch of templates efficiently."""
        templates = []

        # Load templates concurrently
        tasks = []
        for template_id in template_ids:
            task = redis_service.get(template_id)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for template_id, result in zip(template_ids, results):
            if isinstance(result, Exception) or not result:
                continue

            try:
                template = GameTemplate.parse_obj(result)

                # Apply filters
                if await self._template_matches_filters(template, request):
                    templates.append(template)

            except Exception as e:
                logger.warning("Failed to parse template", template_id=template_id, error=str(e))
                continue

        return templates

    async def _template_matches_filters(
        self, template: GameTemplate, request: TemplateSearchRequest
    ) -> bool:
        """Check if template matches search filters."""
        if not template.is_active:
            return False

        if request.game_type and template.metadata.game_type != request.game_type:
            return False

        if request.engine and template.metadata.engine != request.engine:
            return False

        if request.difficulty and template.metadata.difficulty != request.difficulty:
            return False

        if request.tags:
            if not any(tag in template.metadata.tags for tag in request.tags):
                return False

        if request.min_rating and template.rating:
            if template.rating < request.min_rating:
                return False

        if request.query:
            search_text = f"{template.metadata.name} {template.metadata.description}".lower()
            if request.query.lower() not in search_text:
                return False

        return True

    async def _sort_templates_async(
        self, templates: List[GameTemplate], request: TemplateSearchRequest
    ) -> List[GameTemplate]:
        """Sort templates efficiently."""
        if not templates:
            return templates

        reverse = request.sort_order == "desc"

        if request.sort_by == "popularity":
            templates.sort(key=lambda t: t.usage_count or 0, reverse=reverse)
        elif request.sort_by == "rating":
            templates.sort(key=lambda t: t.rating or 0, reverse=reverse)
        elif request.sort_by == "created_at":
            templates.sort(key=lambda t: t.created_at, reverse=reverse)
        elif request.sort_by == "name":
            templates.sort(key=lambda t: t.metadata.name.lower(), reverse=reverse)

        return templates

    async def _instantiate_code_async(
        self, code_template: str, variables: List[Any], values: Dict[str, Any]
    ) -> str:
        """Instantiate template code efficiently."""
        import re

        instantiated_code = code_template

        # Create replacement map
        replacements = {}
        for variable in variables:
            placeholder = f"{{{{{variable.name}}}}}"
            value = values.get(variable.name, variable.default_value)

            # Convert value to string safely
            if isinstance(value, bool):
                replacements[placeholder] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                replacements[placeholder] = str(value)
            else:
                # Escape HTML entities for security
                import html

                replacements[placeholder] = html.escape(str(value))

        # Apply all replacements efficiently
        for placeholder, value in replacements.items():
            instantiated_code = instantiated_code.replace(placeholder, value)

        return instantiated_code

    async def _validate_template_async(
        self, code_template: str, variables: List[Any]
    ) -> TemplateValidationResult:
        """Validate template asynchronously."""
        try:
            # Run validation in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._validate_template_sync, code_template, variables
            )
        except Exception as e:
            logger.error("Template validation failed", error=str(e))
            return TemplateValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=[],
                missing_variables=[],
                unused_variables=[],
                code_metrics={},
            )

    def _validate_template_sync(
        self, code_template: str, variables: List[Any]
    ) -> TemplateValidationResult:
        """Synchronous template validation."""
        errors = []
        warnings = []
        missing_variables = []
        unused_variables = []

        # Basic code validation
        is_valid, code_issues = validator.validate_game_code(code_template)
        if not is_valid:
            errors.extend(code_issues)

        # Variable validation
        variable_names = {var.name for var in variables}

        import re

        used_variables = set(re.findall(r"\{\{(\w+)\}\}", code_template))

        for used_var in used_variables:
            if used_var not in variable_names:
                missing_variables.append(used_var)

        for var_name in variable_names:
            if var_name not in used_variables:
                unused_variables.append(var_name)

        # Quick complexity check
        code_metrics = {
            "size_bytes": len(code_template.encode("utf-8")),
            "lines": len(code_template.split("\n")),
            "variables": len(variables),
        }

        if code_metrics["size_bytes"] > 100000:
            warnings.append("Template is quite large")

        final_is_valid = len(errors) == 0 and len(missing_variables) == 0

        return TemplateValidationResult(
            is_valid=final_is_valid,
            errors=errors,
            warnings=warnings,
            missing_variables=missing_variables,
            unused_variables=unused_variables,
            code_metrics=code_metrics,
        )

    async def _validate_instantiated_code_async(self, code: str) -> Tuple[bool, List[str]]:
        """Validate instantiated code asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, validator.validate_game_code, code)
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]

    async def _generate_template_id_async(self, name: str) -> str:
        """Generate unique template ID asynchronously."""
        import re
        import uuid

        # Create base ID from name
        base_id = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        base_id = base_id[:30]  # Limit length

        # Ensure uniqueness
        for i in range(100):  # Max 100 attempts
            if i == 0:
                template_id = base_id
            else:
                template_id = f"{base_id}_{i}"

            exists = await redis_service.exists(f"template:{template_id}")
            if not exists:
                return template_id

        # Fallback to UUID
        return f"{base_id}_{uuid.uuid4().hex[:8]}"

    # Circuit breaker implementation

    async def _circuit_breaker_check(self) -> bool:
        """Check circuit breaker state."""
        if self._circuit_breaker["state"] == "CLOSED":
            return True

        if self._circuit_breaker["state"] == "OPEN":
            # Check if enough time has passed to try half-open
            if self._circuit_breaker["last_failure"] and datetime.utcnow() - self._circuit_breaker[
                "last_failure"
            ] > timedelta(seconds=60):
                self._circuit_breaker["state"] = "HALF_OPEN"
                return True
            return False

        # HALF_OPEN state - allow one request
        return True

    async def _circuit_breaker_success(self):
        """Record successful operation."""
        self._circuit_breaker["failures"] = 0
        self._circuit_breaker["state"] = "CLOSED"

    async def _circuit_breaker_failure(self):
        """Record failed operation."""
        self._circuit_breaker["failures"] += 1
        self._circuit_breaker["last_failure"] = datetime.utcnow()

        if self._circuit_breaker["failures"] >= 5:
            self._circuit_breaker["state"] = "OPEN"

    # Async background tasks

    async def _load_default_templates_async(self):
        """Load default templates asynchronously."""
        try:
            for game_type, template_info in DEFAULT_TEMPLATES.items():
                template_id = f"default_{game_type.value}"

                # Check if already exists
                if await redis_service.exists(f"template:{template_id}"):
                    continue

                # Create basic template
                template_code = self._create_basic_template(game_type, template_info)

                template = GameTemplate(
                    id=template_id,
                    metadata=template_info,
                    code_template=template_code,
                    variables=[],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    usage_count=0,
                    is_active=True,
                )

                # Store in Redis
                await redis_service.set(f"template:{template_id}", template.dict(), ttl=86400)

                # Initialize usage stats
                await self._initialize_usage_stats_async(template_id)

            logger.info("Default templates loaded asynchronously")

        except Exception as e:
            logger.error("Failed to load default templates", error=str(e))

    async def _increment_usage_count_async(self, template_id: str):
        """Increment usage count asynchronously."""
        try:
            await redis_service.increment(f"template_usage:{template_id}")
        except Exception as e:
            logger.error("Failed to increment usage count", template_id=template_id, error=str(e))

    async def _track_template_usage_async(self, template_id: str, success: bool):
        """Track template usage asynchronously."""
        try:
            await redis_service.increment(f"template_uses:{template_id}")
            if success:
                await redis_service.increment(f"template_success:{template_id}")
            else:
                await redis_service.increment(f"template_failure:{template_id}")
        except Exception as e:
            logger.error("Failed to track template usage", template_id=template_id, error=str(e))

    async def _initialize_usage_stats_async(self, template_id: str):
        """Initialize usage statistics asynchronously."""
        try:
            stats = {
                "template_id": template_id,
                "total_uses": 0,
                "unique_users": 0,
                "successful_generations": 0,
                "failed_generations": 0,
                "created_at": datetime.utcnow().isoformat(),
            }
            await redis_service.set(f"template_stats:{template_id}", stats, ttl=86400)
        except Exception as e:
            logger.error("Failed to initialize usage stats", template_id=template_id, error=str(e))

    # Resource cleanup

    async def cleanup_resources(self):
        """Clean up resources for graceful shutdown."""
        try:
            await self.template_cache.clear()
            await self.usage_cache.clear()
            logger.info("Template manager resources cleaned up")
        except Exception as e:
            logger.error("Failed to cleanup template manager resources", error=str(e))

    def _create_basic_template(self, game_type: GameType, template_info: Dict[str, Any]) -> str:
        """Create basic template code for a game type."""

        # This would contain actual game template code
        # For now, return a basic HTML template
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{"game_title"}}}} - {template_info["name"]}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #000;
            font-family: Arial, sans-serif;
        }}
        #game-container {{
            text-align: center;
        }}
        canvas {{
            border: 1px solid #333;
        }}
    </style>
</head>
<body>
    <div id="game-container">
        <h1>{{{{"game_title"}}}}</h1>
        <canvas id="game-canvas" width="800" height="600"></canvas>
        <p>Basic {game_type.value} game template</p>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.min.js"></script>
    <script>
        // Basic {game_type.value} game code would go here
        console.log("Basic {game_type.value} template loaded");
    </script>
</body>
</html>"""
