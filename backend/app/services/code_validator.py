"""
Code validator service for comprehensive code safety validation.
Provides security checking, quality analysis, and safety validation for generated game code.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from bs4 import BeautifulSoup

from ..config import settings
from ..models.game_models import CodeValidationResult
from ..utils.constants import CODE_VALIDATION, ValidationLevel
from ..utils.validation import ContentValidator, SecurityValidator

logger = structlog.get_logger(__name__)


class CodeValidationError(Exception):
    """Code validation specific errors."""

    pass


class CodeValidator:
    """Comprehensive code validation and security checking."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.MODERATE):
        self.validation_level = validation_level
        self.security_validator = SecurityValidator()
        self.content_validator = ContentValidator()

        # Security patterns to detect
        self.dangerous_patterns = [
            r"eval\s*\(",
            r"Function\s*\(",
            r"setTimeout\s*\(",
            r"setInterval\s*\(",
            r"document\.write\s*\(",
            r"innerHTML\s*=",
            r"outerHTML\s*=",
            r"insertAdjacentHTML\s*\(",
            r"srcdoc\s*=",
            r"javascript:",
            r"vbscript:",
            r"data:text/html",
            r"<iframe[^>]*srcdoc",
            r"<object[^>]*data",
            r"<embed[^>]*src",
        ]

        # Allowed external domains
        self.allowed_domains = CODE_VALIDATION.get("allowed_domains", set())

        # Maximum complexity thresholds
        self.complexity_thresholds = {
            "max_script_tags": CODE_VALIDATION.get("max_script_tags", 10),
            "max_inline_scripts": CODE_VALIDATION.get("max_inline_scripts", 5),
            "max_file_size": settings.game.max_size,
            "max_nesting_depth": 20,
            "max_function_length": 500,
        }

    async def validate_game_code(
        self, code: str, context: Optional[Dict[str, Any]] = None
    ) -> CodeValidationResult:
        """
        Comprehensive validation of game code.

        Args:
            code: HTML game code to validate
            context: Optional validation context

        Returns:
            CodeValidationResult with validation details
        """
        try:
            start_time = datetime.utcnow()

            errors = []
            warnings = []
            security_issues = []
            code_metrics = {}

            # Basic structure validation
            structure_result = await self._validate_html_structure(code)
            errors.extend(structure_result["errors"])
            warnings.extend(structure_result["warnings"])

            # Security validation
            security_result = await self._validate_security(code)
            errors.extend(security_result["errors"])
            security_issues.extend(security_result["security_issues"])

            # Content validation
            content_result = await self._validate_content(code)
            warnings.extend(content_result["warnings"])

            # Code quality analysis
            quality_result = await self._analyze_code_quality(code)
            warnings.extend(quality_result["warnings"])
            code_metrics.update(quality_result["metrics"])

            # Performance validation
            performance_result = await self._validate_performance(code)
            warnings.extend(performance_result["warnings"])

            # Accessibility checks
            if self.validation_level in [ValidationLevel.STRICT, ValidationLevel.MODERATE]:
                accessibility_result = await self._validate_accessibility(code)
                warnings.extend(accessibility_result["warnings"])

            # Determine overall validity
            is_valid = len(errors) == 0 and len(security_issues) == 0

            # Apply strict mode additional checks
            if self.validation_level == ValidationLevel.STRICT:
                strict_result = await self._apply_strict_validation(code)
                errors.extend(strict_result["errors"])
                if len(strict_result["errors"]) > 0:
                    is_valid = False

            validation_time = (datetime.utcnow() - start_time).total_seconds()

            result = CodeValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                security_issues=security_issues,
                code_metrics={
                    **code_metrics,
                    "validation_time": validation_time,
                    "validation_level": self.validation_level.value,
                },
            )

            logger.info(
                "Code validation completed",
                is_valid=is_valid,
                errors_count=len(errors),
                warnings_count=len(warnings),
                security_issues_count=len(security_issues),
                validation_time=validation_time,
            )

            return result

        except Exception as e:
            logger.error("Code validation failed", error=str(e))
            return CodeValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {str(e)}"],
                warnings=[],
                security_issues=[],
                code_metrics={"error": str(e)},
            )

    async def _validate_html_structure(self, code: str) -> Dict[str, List[str]]:
        """Validate HTML structure and required elements."""
        errors = []
        warnings = []

        try:
            # Check for basic HTML structure
            if not re.search(r"<!DOCTYPE\s+html>", code, re.IGNORECASE):
                errors.append("Missing DOCTYPE declaration")

            if not re.search(r"<html[^>]*>", code, re.IGNORECASE):
                errors.append("Missing <html> tag")

            if not re.search(r"</html>", code, re.IGNORECASE):
                errors.append("Missing closing </html> tag")

            if not re.search(r"<head[^>]*>", code, re.IGNORECASE):
                errors.append("Missing <head> section")

            if not re.search(r"<body[^>]*>", code, re.IGNORECASE):
                errors.append("Missing <body> section")

            # Parse with BeautifulSoup for detailed analysis
            soup = BeautifulSoup(code, "html.parser")

            # Check for meta charset
            charset_meta = soup.find("meta", attrs={"charset": True})
            if not charset_meta:
                warnings.append("Missing charset meta tag")

            # Check for viewport meta
            viewport_meta = soup.find("meta", attrs={"name": "viewport"})
            if not viewport_meta:
                warnings.append("Missing viewport meta tag")

            # Check for title
            title_tag = soup.find("title")
            if not title_tag or not title_tag.string:
                warnings.append("Missing or empty title tag")

            # Validate nesting depth
            max_depth = self._calculate_nesting_depth(soup)
            if max_depth > self.complexity_thresholds["max_nesting_depth"]:
                warnings.append(f"Deep HTML nesting detected (depth: {max_depth})")

        except Exception as e:
            errors.append(f"HTML structure validation error: {str(e)}")

        return {"errors": errors, "warnings": warnings}

    async def _validate_security(self, code: str) -> Dict[str, List[str]]:
        """Validate code for security issues."""
        errors = []
        security_issues = []

        try:
            # Check for dangerous patterns
            for pattern in self.dangerous_patterns:
                matches = re.findall(pattern, code, re.IGNORECASE)
                if matches:
                    security_issues.append(f"Dangerous pattern detected: {pattern}")

            # Check for external resource domains
            external_links = re.findall(
                r'(?:src|href)\s*=\s*["\']?(https?://[^"\'>\s]+)', code, re.IGNORECASE
            )
            for link in external_links:
                from urllib.parse import urlparse

                domain = urlparse(link).netloc
                if domain not in self.allowed_domains:
                    security_issues.append(f"Unauthorized external domain: {domain}")

            # Check for inline event handlers
            event_handlers = re.findall(r"on\w+\s*=", code, re.IGNORECASE)
            if event_handlers:
                security_issues.append(
                    f"Inline event handlers detected: {len(event_handlers)} instances"
                )

            # Check for data URIs
            data_uris = re.findall(r'data:[^"\'>\s]+', code, re.IGNORECASE)
            suspicious_data_uris = [
                uri for uri in data_uris if "javascript" in uri.lower() or "vbscript" in uri.lower()
            ]
            if suspicious_data_uris:
                security_issues.append("Suspicious data URIs detected")

            # Check for form elements (potential data collection)
            if re.search(r"<form[^>]*>", code, re.IGNORECASE):
                security_issues.append("Form element detected - potential data collection")

            # Check for WebSocket connections
            if re.search(r"new\s+WebSocket\s*\(", code, re.IGNORECASE):
                security_issues.append("WebSocket connection detected")

            # Check for localStorage/sessionStorage usage
            if re.search(r"(?:localStorage|sessionStorage)", code, re.IGNORECASE):
                security_issues.append("Local storage usage detected")

        except Exception as e:
            errors.append(f"Security validation error: {str(e)}")

        return {"errors": errors, "security_issues": security_issues}

    async def _validate_content(self, code: str) -> Dict[str, List[str]]:
        """Validate content appropriateness."""
        warnings = []

        try:
            # Check for potentially inappropriate content
            inappropriate_patterns = [
                r"\b(?:violence|kill|death|blood|gore)\b",
                r"\b(?:adult|sexual|explicit)\b",
                r"\b(?:hack|exploit|virus|malware)\b",
                r"\b(?:cheat|crack|pirate)\b",
            ]

            content_lower = code.lower()
            for pattern in inappropriate_patterns:
                if re.search(pattern, content_lower):
                    warnings.append("Potentially inappropriate content detected")
                    break

            # Check for excessive external dependencies
            script_tags = re.findall(r"<script[^>]*src=[^>]*>", code, re.IGNORECASE)
            if len(script_tags) > 5:
                warnings.append(f"Many external scripts detected: {len(script_tags)}")

        except Exception as e:
            warnings.append(f"Content validation error: {str(e)}")

        return {"warnings": warnings}

    async def _analyze_code_quality(self, code: str) -> Dict[str, Any]:
        """Analyze code quality and metrics."""
        warnings = []
        metrics = {}

        try:
            # Basic metrics
            metrics["size_bytes"] = len(code.encode("utf-8"))
            metrics["lines"] = len(code.split("\n"))

            # Parse HTML
            soup = BeautifulSoup(code, "html.parser")

            # Count elements
            metrics["total_elements"] = len(soup.find_all())
            metrics["script_tags"] = len(soup.find_all("script"))
            metrics["style_tags"] = len(soup.find_all("style"))
            metrics["img_tags"] = len(soup.find_all("img"))

            # Check for inline styles
            inline_styles = soup.find_all(attrs={"style": True})
            metrics["inline_styles"] = len(inline_styles)
            if len(inline_styles) > 10:
                warnings.append("Excessive inline styles detected")

            # Analyze JavaScript content
            script_content = ""
            for script in soup.find_all("script"):
                if script.string:
                    script_content += script.string + "\n"

            if script_content:
                js_metrics = self._analyze_javascript_quality(script_content)
                metrics.update(js_metrics)

                if js_metrics.get("complexity_score", 0) > 100:
                    warnings.append("High JavaScript complexity detected")

            # Check file size
            if metrics["size_bytes"] > self.complexity_thresholds["max_file_size"]:
                warnings.append(f"Large file size: {metrics['size_bytes']} bytes")

            # Check script count
            if metrics["script_tags"] > self.complexity_thresholds["max_script_tags"]:
                warnings.append(f"Too many script tags: {metrics['script_tags']}")

        except Exception as e:
            warnings.append(f"Code quality analysis error: {str(e)}")
            metrics["analysis_error"] = str(e)

        return {"warnings": warnings, "metrics": metrics}

    async def _validate_performance(self, code: str) -> Dict[str, List[str]]:
        """Validate performance aspects."""
        warnings = []

        try:
            # Check for potential performance issues
            soup = BeautifulSoup(code, "html.parser")

            # Check for large images without optimization hints
            images = soup.find_all("img")
            for img in images:
                src = img.get("src", "")
                if not any(hint in src for hint in ["width=", "height=", "w_", "h_"]):
                    if len(images) > 5:  # Only warn if many images
                        warnings.append("Images without size hints detected")
                        break

            # Check for synchronous script loading
            scripts = soup.find_all("script", src=True)
            sync_scripts = [s for s in scripts if not s.get("async") and not s.get("defer")]
            if len(sync_scripts) > 3:
                warnings.append("Multiple synchronous scripts may impact performance")

            # Check for CSS imports
            if re.search(r"@import\s+url\(", code, re.IGNORECASE):
                warnings.append("CSS imports can impact performance")

            # Check for excessive DOM elements
            total_elements = len(soup.find_all())
            if total_elements > 1000:
                warnings.append(f"Many DOM elements detected: {total_elements}")

        except Exception as e:
            warnings.append(f"Performance validation error: {str(e)}")

        return {"warnings": warnings}

    async def _validate_accessibility(self, code: str) -> Dict[str, List[str]]:
        """Validate accessibility features."""
        warnings = []

        try:
            soup = BeautifulSoup(code, "html.parser")

            # Check for alt text on images
            images = soup.find_all("img")
            images_without_alt = [img for img in images if not img.get("alt")]
            if images_without_alt:
                warnings.append(f"Images without alt text: {len(images_without_alt)}")

            # Check for language attribute
            html_tag = soup.find("html")
            if html_tag and not html_tag.get("lang"):
                warnings.append("Missing language attribute on html element")

            # Check for proper heading structure
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            if not headings:
                warnings.append("No heading elements found")

            # Check for form labels
            inputs = soup.find_all("input")
            for input_elem in inputs:
                input_id = input_elem.get("id")
                if input_id:
                    label = soup.find("label", attrs={"for": input_id})
                    if not label and not input_elem.get("aria-label"):
                        warnings.append("Form inputs without proper labels")
                        break

        except Exception as e:
            warnings.append(f"Accessibility validation error: {str(e)}")

        return {"warnings": warnings}

    async def _apply_strict_validation(self, code: str) -> Dict[str, List[str]]:
        """Apply strict validation rules."""
        errors = []

        try:
            # Strict security checks
            if re.search(r"innerHTML\s*=", code, re.IGNORECASE):
                errors.append("innerHTML usage not allowed in strict mode")

            # No external resources in strict mode
            if re.search(r"https?://", code, re.IGNORECASE):
                errors.append("External resources not allowed in strict mode")

            # Validate all JavaScript is parseable
            soup = BeautifulSoup(code, "html.parser")
            for script in soup.find_all("script"):
                if script.string:
                    try:
                        # Basic JavaScript syntax check (simplified)
                        js_content = script.string.strip()
                        if js_content and not self._validate_javascript_syntax(js_content):
                            errors.append("JavaScript syntax validation failed")
                    except Exception:
                        errors.append("JavaScript syntax validation failed")

        except Exception as e:
            errors.append(f"Strict validation error: {str(e)}")

        return {"errors": errors}

    def _analyze_javascript_quality(self, js_content: str) -> Dict[str, Any]:
        """Analyze JavaScript code quality."""
        metrics = {}

        try:
            # Count functions
            function_matches = re.findall(r"function\s+\w+\s*\(", js_content)
            arrow_functions = re.findall(r"=>", js_content)
            metrics["function_count"] = len(function_matches) + len(arrow_functions)

            # Count variables
            var_matches = re.findall(r"(?:var|let|const)\s+\w+", js_content)
            metrics["variable_count"] = len(var_matches)

            # Count conditionals and loops
            conditionals = re.findall(r"\b(?:if|else|switch)\b", js_content)
            loops = re.findall(r"\b(?:for|while|do)\b", js_content)
            metrics["conditional_count"] = len(conditionals)
            metrics["loop_count"] = len(loops)

            # Calculate complexity score
            metrics["complexity_score"] = (
                metrics["function_count"] * 2
                + metrics["variable_count"] * 0.5
                + metrics["conditional_count"] * 1.5
                + metrics["loop_count"] * 2
            )

            # Check for long functions
            function_blocks = re.findall(r"function[^{]*{[^}]*}", js_content, re.DOTALL)
            long_functions = [
                f
                for f in function_blocks
                if len(f) > self.complexity_thresholds["max_function_length"]
            ]
            metrics["long_function_count"] = len(long_functions)

        except Exception as e:
            metrics["js_analysis_error"] = str(e)

        return metrics

    def _validate_javascript_syntax(self, js_content: str) -> bool:
        """Basic JavaScript syntax validation."""
        try:
            # Check balanced braces
            brace_count = js_content.count("{") - js_content.count("}")
            if brace_count != 0:
                return False

            # Check balanced parentheses
            paren_count = js_content.count("(") - js_content.count(")")
            if paren_count != 0:
                return False

            # Check for basic syntax errors
            if re.search(r"[^a-zA-Z_$]var\s*[^a-zA-Z_$]", js_content):
                return False

            return True

        except Exception:
            return False

    def _calculate_nesting_depth(self, soup) -> int:
        """Calculate maximum nesting depth of HTML elements."""

        def get_depth(element, current_depth=0):
            if not hasattr(element, "children"):
                return current_depth

            max_child_depth = current_depth
            for child in element.children:
                if hasattr(child, "name") and child.name:
                    child_depth = get_depth(child, current_depth + 1)
                    max_child_depth = max(max_child_depth, child_depth)

            return max_child_depth

        try:
            return get_depth(soup)
        except Exception:
            return 0

    async def validate_code_modification(
        self, original_code: str, modified_code: str
    ) -> Dict[str, Any]:
        """
        Validate that code modification is safe.

        Args:
            original_code: Original game code
            modified_code: Modified game code

        Returns:
            Dictionary with modification validation results
        """
        try:
            # Validate both versions
            original_result = await self.validate_game_code(original_code)
            modified_result = await self.validate_game_code(modified_code)

            # Compare security issues
            new_security_issues = []
            for issue in modified_result.security_issues:
                if issue not in original_result.security_issues:
                    new_security_issues.append(issue)

            # Check if modification introduced problems
            modification_safe = modified_result.is_valid and len(new_security_issues) == 0

            return {
                "modification_safe": modification_safe,
                "original_valid": original_result.is_valid,
                "modified_valid": modified_result.is_valid,
                "new_security_issues": new_security_issues,
                "new_errors": [
                    e for e in modified_result.errors if e not in original_result.errors
                ],
                "security_regression": len(new_security_issues) > 0,
            }

        except Exception as e:
            logger.error("Code modification validation failed", error=str(e))
            return {"modification_safe": False, "error": str(e)}
