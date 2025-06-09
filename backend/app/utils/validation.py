"""
Input validation utilities for AI Game Generator.
Provides security validation, content filtering, and data sanitization.
"""

import ast
import html
import json
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..config import settings
from .constants import BLOCKED_KEYWORDS, CODE_VALIDATION, ValidationLevel


class ValidationError(Exception):
    """Custom validation error."""

    pass


class SecurityValidator:
    """Security-focused validation utilities."""

    @staticmethod
    def validate_html_content(content: str) -> Tuple[bool, List[str]]:
        """
        Validate HTML content for security issues.

        Args:
            content: HTML content to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for blocked patterns
        for pattern in CODE_VALIDATION["blocked_patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Blocked pattern detected: {pattern}")

        # Check for required patterns
        for pattern in CODE_VALIDATION["required_patterns"]:
            if not re.search(pattern, content, re.IGNORECASE):
                issues.append(f"Required pattern missing: {pattern}")

        # Count script tags
        script_count = len(re.findall(r"<script.*?>", content, re.IGNORECASE))
        if script_count > CODE_VALIDATION["max_script_tags"]:
            issues.append(f"Too many script tags: {script_count}")

        # Check for inline event handlers
        event_handlers = re.findall(r"on\w+\s*=", content, re.IGNORECASE)
        if event_handlers:
            issues.append(f"Inline event handlers detected: {event_handlers}")

        # Check for external resources
        external_links = re.findall(
            r'(?:src|href)\s*=\s*["\']?(https?://[^"\'>\s]+)', content, re.IGNORECASE
        )
        for link in external_links:
            domain = urllib.parse.urlparse(link).netloc
            if domain not in CODE_VALIDATION["allowed_domains"]:
                issues.append(f"Unauthorized external domain: {domain}")

        return len(issues) == 0, issues

    @staticmethod
    def validate_javascript_code(code: str) -> Tuple[bool, List[str]]:
        """
        Validate JavaScript code for security issues.

        Args:
            code: JavaScript code to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for dangerous functions
        dangerous_patterns = [
            r"eval\s*\(",
            r"Function\s*\(",
            r"setTimeout\s*\(",
            r"setInterval\s*\(",
            r"document\.write\s*\(",
            r"innerHTML\s*=",
            r"outerHTML\s*=",
            r"insertAdjacentHTML\s*\(",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Dangerous JavaScript pattern: {pattern}")

        # Check for blocked keywords
        for keyword in BLOCKED_KEYWORDS:
            if keyword.lower() in code.lower():
                issues.append(f"Blocked keyword detected: {keyword}")

        # Try to parse as AST (basic syntax check)
        try:
            # Remove script tags and extract JavaScript
            js_code = re.sub(r"<script[^>]*>", "", code, flags=re.IGNORECASE)
            js_code = re.sub(r"</script>", "", js_code, flags=re.IGNORECASE)

            # Basic syntax validation using simple heuristics
            # (Full JS parsing would require a JS parser)
            if js_code.strip():
                # Check for balanced braces
                if js_code.count("{") != js_code.count("}"):
                    issues.append("Unbalanced braces in JavaScript")

                # Check for balanced parentheses
                if js_code.count("(") != js_code.count(")"):
                    issues.append("Unbalanced parentheses in JavaScript")

        except Exception as e:
            issues.append(f"JavaScript syntax error: {str(e)}")

        return len(issues) == 0, issues

    @staticmethod
    def sanitize_user_input(input_text: str, max_length: int = 5000) -> str:
        """
        Sanitize user input for safe processing.

        Args:
            input_text: Raw user input
            max_length: Maximum allowed length

        Returns:
            Sanitized input text
        """
        if not input_text:
            return ""

        # Truncate if too long
        if len(input_text) > max_length:
            input_text = input_text[:max_length]

        # HTML escape
        sanitized = html.escape(input_text)

        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")

        # Normalize whitespace
        sanitized = " ".join(sanitized.split())

        return sanitized.strip()


class ContentValidator:
    """Content validation utilities."""

    @staticmethod
    def validate_game_prompt(prompt: str) -> Tuple[bool, List[str]]:
        """
        Validate game generation prompt.

        Args:
            prompt: Game description prompt

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if not prompt or not prompt.strip():
            issues.append("Prompt cannot be empty")
            return False, issues

        if len(prompt) < 10:
            issues.append("Prompt too short (minimum 10 characters)")

        if len(prompt) > 5000:
            issues.append("Prompt too long (maximum 5000 characters)")

        # Check for inappropriate content (basic)
        inappropriate_patterns = [
            r"\b(violence|kill|death|blood|gore)\b",
            r"\b(adult|sexual|explicit)\b",
            r"\b(hack|exploit|virus|malware)\b",
        ]

        for pattern in inappropriate_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                issues.append(f"Potentially inappropriate content detected")
                break

        # Check for excessive repetition
        words = prompt.lower().split()
        if len(words) > 10:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            max_repetition = max(word_counts.values())
            if max_repetition > len(words) * 0.3:  # More than 30% repetition
                issues.append("Excessive word repetition detected")

        return len(issues) == 0, issues

    @staticmethod
    def validate_chat_message(message: str) -> Tuple[bool, List[str]]:
        """
        Validate chat message content.

        Args:
            message: Chat message text

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if not message or not message.strip():
            issues.append("Message cannot be empty")
            return False, issues

        if len(message) > 2000:
            issues.append("Message too long (maximum 2000 characters)")

        # Check for spam patterns
        if len(set(message.lower())) < len(message) * 0.3:  # Low character diversity
            issues.append("Message appears to be spam")

        # Check for excessive caps
        caps_ratio = sum(1 for c in message if c.isupper()) / len(message)
        if caps_ratio > 0.7 and len(message) > 20:
            issues.append("Excessive use of capital letters")

        return len(issues) == 0, issues


class DataValidator:
    """Data structure validation utilities."""

    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """
        Validate session ID format.

        Args:
            session_id: Session identifier

        Returns:
            True if valid, False otherwise
        """
        if not session_id:
            return False

        # Should be alphanumeric with underscores, reasonable length
        pattern = r"^[a-zA-Z0-9_-]{10,50}$"
        return bool(re.match(pattern, session_id))

    @staticmethod
    def validate_game_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate game metadata structure.

        Args:
            metadata: Game metadata dictionary

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        required_fields = ["game_type", "engine", "difficulty"]

        for field in required_fields:
            if field not in metadata:
                issues.append(f"Missing required field: {field}")

        # Validate game_type
        if "game_type" in metadata:
            valid_types = ["platformer", "shooter", "puzzle", "racing", "arcade"]
            if metadata["game_type"] not in valid_types:
                issues.append(f"Invalid game_type: {metadata['game_type']}")

        # Validate features list
        if "features" in metadata:
            if not isinstance(metadata["features"], list):
                issues.append("Features must be a list")
            elif len(metadata["features"]) > 50:
                issues.append("Too many features (maximum 50)")

        return len(issues) == 0, issues

    @staticmethod
    def validate_json_structure(
        json_str: str, max_size: int = 1024 * 1024
    ) -> Tuple[bool, Any, List[str]]:
        """
        Validate JSON string structure and content.

        Args:
            json_str: JSON string to validate
            max_size: Maximum size in bytes

        Returns:
            Tuple of (is_valid, parsed_data, list_of_issues)
        """
        issues = []
        parsed_data = None

        if len(json_str.encode("utf-8")) > max_size:
            issues.append(f"JSON too large (maximum {max_size} bytes)")
            return False, None, issues

        try:
            parsed_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON format: {str(e)}")
            return False, None, issues

        # Check for deeply nested structures
        def check_depth(obj, current_depth=0, max_depth=10):
            if current_depth > max_depth:
                return False
            if isinstance(obj, dict):
                return all(check_depth(v, current_depth + 1, max_depth) for v in obj.values())
            elif isinstance(obj, list):
                return all(check_depth(item, current_depth + 1, max_depth) for item in obj)
            return True

        if not check_depth(parsed_data):
            issues.append("JSON structure too deeply nested")

        return len(issues) == 0, parsed_data, issues


class RateLimitValidator:
    """Rate limiting validation utilities."""

    @staticmethod
    def validate_request_frequency(
        timestamps: List[datetime], window_minutes: int = 1, max_requests: int = 10
    ) -> bool:
        """
        Validate request frequency within a time window.

        Args:
            timestamps: List of request timestamps
            window_minutes: Time window in minutes
            max_requests: Maximum allowed requests in window

        Returns:
            True if within limits, False otherwise
        """
        if not timestamps:
            return True

        now = datetime.utcnow()
        window_start = now - datetime.timedelta(minutes=window_minutes)

        recent_requests = [ts for ts in timestamps if ts >= window_start]

        return len(recent_requests) <= max_requests


class ComprehensiveValidator:
    """Main validator class that combines all validation types."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.MODERATE):
        self.validation_level = validation_level
        self.security = SecurityValidator()
        self.content = ContentValidator()
        self.data = DataValidator()
        self.rate_limit = RateLimitValidator()

    def validate_game_generation_request(
        self, prompt: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation for game generation requests.

        Args:
            prompt: Game description prompt
            metadata: Optional metadata

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        all_issues = []

        # Validate prompt
        prompt_valid, prompt_issues = self.content.validate_game_prompt(prompt)
        all_issues.extend(prompt_issues)

        # Validate metadata if provided
        if metadata:
            metadata_valid, metadata_issues = self.data.validate_game_metadata(metadata)
            all_issues.extend(metadata_issues)

        # Additional strict validation for production
        if self.validation_level == ValidationLevel.STRICT:
            # More stringent content checks
            if len(prompt.split()) < 5:
                all_issues.append("Prompt must contain at least 5 words")

        return len(all_issues) == 0, all_issues

    def validate_game_code(self, code: str) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation for generated game code.

        Args:
            code: HTML game code

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        all_issues = []

        # HTML validation
        html_valid, html_issues = self.security.validate_html_content(code)
        all_issues.extend(html_issues)

        # JavaScript validation
        js_valid, js_issues = self.security.validate_javascript_code(code)
        all_issues.extend(js_issues)

        # Size validation
        if len(code.encode("utf-8")) > settings.game.max_size:
            all_issues.append(f"Game code too large (maximum {settings.game.max_size} bytes)")

        return len(all_issues) == 0, all_issues

    def validate_chat_request(self, message: str, session_id: str) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation for chat requests.

        Args:
            message: Chat message
            session_id: Session identifier

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        all_issues = []

        # Message validation
        message_valid, message_issues = self.content.validate_chat_message(message)
        all_issues.extend(message_issues)

        # Session ID validation
        if not self.data.validate_session_id(session_id):
            all_issues.append("Invalid session ID format")

        return len(all_issues) == 0, all_issues


# Global validator instance
validator = ComprehensiveValidator(
    validation_level=ValidationLevel.MODERATE if settings.app.debug else ValidationLevel.STRICT
)
