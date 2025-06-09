"""
Code change detection engine for AI Game Generator.
Provides intelligent diff analysis, change detection, and code comparison utilities.
"""

import difflib
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import structlog

from ..config import settings
from ..utils.code_utils import CSSParser, HTMLParser, JavaScriptParser

logger = structlog.get_logger(__name__)


@dataclass
class CodeChange:
    """Represents a single code change."""

    change_type: str  # 'addition', 'deletion', 'modification'
    line_number: int
    old_content: Optional[str]
    new_content: Optional[str]
    context: str  # 'html', 'css', 'javascript'
    description: str


@dataclass
class DiffSummary:
    """Summary of differences between two code versions."""

    total_changes: int
    additions: int
    deletions: int
    modifications: int
    files_changed: int
    change_percentage: float
    significant_changes: List[str]
    technical_changes: List[CodeChange]


class DiffEngine:
    """Main diff analysis engine."""

    def __init__(self):
        self.html_parser = HTMLParser()
        self.js_parser = JavaScriptParser()
        self.css_parser = CSSParser()

    def analyze_code_diff(self, old_code: str, new_code: str) -> DiffSummary:
        """
        Comprehensive analysis of differences between two code versions.

        Args:
            old_code: Original code version
            new_code: Modified code version

        Returns:
            DiffSummary with detailed change analysis
        """
        try:
            # Quick check for identical code
            if old_code == new_code:
                return DiffSummary(
                    total_changes=0,
                    additions=0,
                    deletions=0,
                    modifications=0,
                    files_changed=0,
                    change_percentage=0.0,
                    significant_changes=["No changes detected"],
                    technical_changes=[],
                )

            # Perform line-by-line diff
            old_lines = old_code.splitlines()
            new_lines = new_code.splitlines()

            diff = list(
                difflib.unified_diff(
                    old_lines, new_lines, fromfile="original", tofile="modified", lineterm="", n=3
                )
            )

            # Analyze diff statistics
            additions = len([line for line in diff if line.startswith("+")])
            deletions = len([line for line in diff if line.startswith("-")])

            # Calculate change percentage
            total_lines = max(len(old_lines), len(new_lines), 1)
            change_percentage = (additions + deletions) / total_lines * 100

            # Detect specific change types
            technical_changes = self._detect_technical_changes(old_code, new_code)
            significant_changes = self._detect_significant_changes(old_code, new_code)

            return DiffSummary(
                total_changes=additions + deletions,
                additions=additions,
                deletions=deletions,
                modifications=min(additions, deletions),
                files_changed=1,
                change_percentage=round(change_percentage, 2),
                significant_changes=significant_changes,
                technical_changes=technical_changes,
            )

        except Exception as e:
            logger.error("Diff analysis failed", error=str(e))
            return DiffSummary(
                total_changes=0,
                additions=0,
                deletions=0,
                modifications=0,
                files_changed=0,
                change_percentage=0.0,
                significant_changes=[f"Analysis failed: {str(e)}"],
                technical_changes=[],
            )

    def _detect_technical_changes(self, old_code: str, new_code: str) -> List[CodeChange]:
        """Detect specific technical changes in the code."""
        changes = []

        try:
            # Analyze HTML structure changes
            changes.extend(self._analyze_html_changes(old_code, new_code))

            # Analyze JavaScript changes
            changes.extend(self._analyze_javascript_changes(old_code, new_code))

            # Analyze CSS changes
            changes.extend(self._analyze_css_changes(old_code, new_code))

        except Exception as e:
            logger.error("Technical change detection failed", error=str(e))

        return changes

    def _analyze_html_changes(self, old_code: str, new_code: str) -> List[CodeChange]:
        """Analyze HTML structure changes."""
        changes = []

        try:
            # Extract HTML elements
            old_elements = self._extract_html_elements(old_code)
            new_elements = self._extract_html_elements(new_code)

            # Find added elements
            added_elements = new_elements - old_elements
            for element in added_elements:
                changes.append(
                    CodeChange(
                        change_type="addition",
                        line_number=0,  # Would need line tracking for exact position
                        old_content=None,
                        new_content=element,
                        context="html",
                        description=f"Added HTML element: {element}",
                    )
                )

            # Find removed elements
            removed_elements = old_elements - new_elements
            for element in removed_elements:
                changes.append(
                    CodeChange(
                        change_type="deletion",
                        line_number=0,
                        old_content=element,
                        new_content=None,
                        context="html",
                        description=f"Removed HTML element: {element}",
                    )
                )

        except Exception as e:
            logger.error("HTML change analysis failed", error=str(e))

        return changes

    def _analyze_javascript_changes(self, old_code: str, new_code: str) -> List[CodeChange]:
        """Analyze JavaScript code changes."""
        changes = []

        try:
            # Extract functions
            old_functions = self._extract_js_functions(old_code)
            new_functions = self._extract_js_functions(new_code)

            # Find added functions
            added_functions = new_functions - old_functions
            for func in added_functions:
                changes.append(
                    CodeChange(
                        change_type="addition",
                        line_number=0,
                        old_content=None,
                        new_content=func,
                        context="javascript",
                        description=f"Added JavaScript function: {func}",
                    )
                )

            # Find removed functions
            removed_functions = old_functions - new_functions
            for func in removed_functions:
                changes.append(
                    CodeChange(
                        change_type="deletion",
                        line_number=0,
                        old_content=func,
                        new_content=None,
                        context="javascript",
                        description=f"Removed JavaScript function: {func}",
                    )
                )

            # Analyze variable changes
            old_vars = self._extract_js_variables(old_code)
            new_vars = self._extract_js_variables(new_code)

            added_vars = new_vars - old_vars
            for var in added_vars:
                changes.append(
                    CodeChange(
                        change_type="addition",
                        line_number=0,
                        old_content=None,
                        new_content=var,
                        context="javascript",
                        description=f"Added JavaScript variable: {var}",
                    )
                )

        except Exception as e:
            logger.error("JavaScript change analysis failed", error=str(e))

        return changes

    def _analyze_css_changes(self, old_code: str, new_code: str) -> List[CodeChange]:
        """Analyze CSS style changes."""
        changes = []

        try:
            # Extract CSS rules
            old_rules = self._extract_css_rules(old_code)
            new_rules = self._extract_css_rules(new_code)

            # Find changed selectors
            old_selectors = set(old_rules.keys())
            new_selectors = set(new_rules.keys())

            # Added selectors
            for selector in new_selectors - old_selectors:
                changes.append(
                    CodeChange(
                        change_type="addition",
                        line_number=0,
                        old_content=None,
                        new_content=selector,
                        context="css",
                        description=f"Added CSS selector: {selector}",
                    )
                )

            # Removed selectors
            for selector in old_selectors - new_selectors:
                changes.append(
                    CodeChange(
                        change_type="deletion",
                        line_number=0,
                        old_content=selector,
                        new_content=None,
                        context="css",
                        description=f"Removed CSS selector: {selector}",
                    )
                )

            # Modified selectors
            for selector in old_selectors & new_selectors:
                if old_rules[selector] != new_rules[selector]:
                    changes.append(
                        CodeChange(
                            change_type="modification",
                            line_number=0,
                            old_content=old_rules[selector],
                            new_content=new_rules[selector],
                            context="css",
                            description=f"Modified CSS for selector: {selector}",
                        )
                    )

        except Exception as e:
            logger.error("CSS change analysis failed", error=str(e))

        return changes

    def _detect_significant_changes(self, old_code: str, new_code: str) -> List[str]:
        """Detect high-level significant changes."""
        significant_changes = []

        try:
            # Color changes
            old_colors = self._extract_colors(old_code)
            new_colors = self._extract_colors(new_code)

            if old_colors != new_colors:
                added_colors = new_colors - old_colors
                removed_colors = old_colors - new_colors

                if added_colors:
                    significant_changes.append(f"Added colors: {', '.join(added_colors)}")
                if removed_colors:
                    significant_changes.append(f"Removed colors: {', '.join(removed_colors)}")

            # Game mechanics changes
            old_mechanics = self._extract_game_mechanics(old_code)
            new_mechanics = self._extract_game_mechanics(new_code)

            added_mechanics = new_mechanics - old_mechanics
            if added_mechanics:
                significant_changes.append(f"Added game mechanics: {', '.join(added_mechanics)}")

            # Script library changes
            old_libs = self._extract_external_libraries(old_code)
            new_libs = self._extract_external_libraries(new_code)

            if old_libs != new_libs:
                significant_changes.append("External library dependencies changed")

            # Size changes
            old_size = len(old_code)
            new_size = len(new_code)
            size_change_percent = abs(new_size - old_size) / max(old_size, 1) * 100

            if size_change_percent > 20:
                direction = "increased" if new_size > old_size else "decreased"
                significant_changes.append(f"Code size {direction} by {size_change_percent:.1f}%")

            # Performance-related changes
            if self._detect_performance_changes(old_code, new_code):
                significant_changes.append("Performance-affecting changes detected")

        except Exception as e:
            logger.error("Significant change detection failed", error=str(e))

        return significant_changes if significant_changes else ["Minor code adjustments"]

    def _extract_html_elements(self, code: str) -> Set[str]:
        """Extract HTML element types from code."""
        elements = set()

        # Find all HTML tags
        tag_pattern = r"<(\w+)(?:\s+[^>]*)?>"
        matches = re.findall(tag_pattern, code, re.IGNORECASE)

        for tag in matches:
            elements.add(tag.lower())

        return elements

    def _extract_js_functions(self, code: str) -> Set[str]:
        """Extract JavaScript function names."""
        functions = set()

        # Function declarations
        func_pattern = r"function\s+(\w+)\s*\("
        matches = re.findall(func_pattern, code)
        functions.update(matches)

        # Arrow functions and function expressions
        arrow_pattern = r"(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|function)"
        matches = re.findall(arrow_pattern, code)
        functions.update(matches)

        return functions

    def _extract_js_variables(self, code: str) -> Set[str]:
        """Extract JavaScript variable names."""
        variables = set()

        var_pattern = r"(?:const|let|var)\s+(\w+)"
        matches = re.findall(var_pattern, code)
        variables.update(matches)

        return variables

    def _extract_css_rules(self, code: str) -> Dict[str, str]:
        """Extract CSS rules and their properties."""
        rules = {}

        try:
            # Extract style blocks
            style_pattern = r"<style[^>]*>(.*?)</style>"
            style_blocks = re.findall(style_pattern, code, re.DOTALL | re.IGNORECASE)

            for style_block in style_blocks:
                # Parse CSS rules
                rule_pattern = r"([^{]+)\s*\{\s*([^}]+)\s*\}"
                rule_matches = re.findall(rule_pattern, style_block)

                for selector, properties in rule_matches:
                    selector = selector.strip()
                    properties = properties.strip()
                    rules[selector] = properties

        except Exception as e:
            logger.error("CSS rule extraction failed", error=str(e))

        return rules

    def _extract_colors(self, code: str) -> Set[str]:
        """Extract color values from code."""
        colors = set()

        # Hex colors
        hex_pattern = r"#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}"
        hex_colors = re.findall(hex_pattern, code)
        colors.update(hex_colors)

        # RGB colors
        rgb_pattern = r"rgb\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)"
        rgb_colors = re.findall(rgb_pattern, code, re.IGNORECASE)
        colors.update(rgb_colors)

        # Named colors
        named_colors = [
            "red",
            "blue",
            "green",
            "yellow",
            "purple",
            "orange",
            "pink",
            "black",
            "white",
            "gray",
            "brown",
            "cyan",
            "magenta",
        ]

        for color in named_colors:
            if re.search(rf"\b{color}\b", code, re.IGNORECASE):
                colors.add(color)

        return colors

    def _extract_game_mechanics(self, code: str) -> Set[str]:
        """Extract game mechanics keywords."""
        mechanics = set()

        mechanic_keywords = [
            "collision",
            "physics",
            "gravity",
            "velocity",
            "acceleration",
            "score",
            "health",
            "lives",
            "level",
            "enemy",
            "player",
            "jump",
            "shoot",
            "move",
            "rotate",
            "scale",
            "animate",
        ]

        code_lower = code.lower()
        for keyword in mechanic_keywords:
            if keyword in code_lower:
                mechanics.add(keyword)

        return mechanics

    def _extract_external_libraries(self, code: str) -> Set[str]:
        """Extract external library URLs."""
        libraries = set()

        # Extract script src attributes
        src_pattern = r'<script[^>]+src=["\']([^"\']+)["\']'
        matches = re.findall(src_pattern, code, re.IGNORECASE)

        for src in matches:
            # Extract library name from URL
            if "cdn.jsdelivr.net" in src or "cdnjs.cloudflare.com" in src:
                # Extract library name
                parts = src.split("/")
                for part in parts:
                    if any(lib in part.lower() for lib in ["phaser", "three", "p5", "jquery"]):
                        libraries.add(part.split("@")[0])  # Remove version
                        break

        return libraries

    def _detect_performance_changes(self, old_code: str, new_code: str) -> bool:
        """Detect changes that might affect performance."""

        # Check for new loops
        old_loops = len(re.findall(r"\b(?:for|while)\b", old_code))
        new_loops = len(re.findall(r"\b(?:for|while)\b", new_code))

        if new_loops > old_loops:
            return True

        # Check for new DOM queries
        old_queries = len(re.findall(r"(?:getElementById|querySelector|getElementsBy)", old_code))
        new_queries = len(re.findall(r"(?:getElementById|querySelector|getElementsBy)", new_code))

        if new_queries > old_queries * 1.5:  # 50% increase
            return True

        # Check for new image/resource loads
        old_resources = len(re.findall(r"(?:img|audio|video|script|link)", old_code, re.IGNORECASE))
        new_resources = len(re.findall(r"(?:img|audio|video|script|link)", new_code, re.IGNORECASE))

        if new_resources > old_resources:
            return True

        return False


class SemanticDiffAnalyzer:
    """Analyzes semantic differences in game code."""

    @staticmethod
    def analyze_gameplay_changes(old_code: str, new_code: str) -> Dict[str, Any]:
        """
        Analyze changes that affect gameplay mechanics.

        Args:
            old_code: Original code
            new_code: Modified code

        Returns:
            Dictionary with gameplay change analysis
        """
        changes = {
            "physics_changes": [],
            "control_changes": [],
            "scoring_changes": [],
            "visual_changes": [],
            "audio_changes": [],
        }

        # Physics changes
        physics_keywords = ["gravity", "velocity", "acceleration", "friction", "bounce"]
        for keyword in physics_keywords:
            old_physics = re.findall(rf"{keyword}[^;,}}]*", old_code, re.IGNORECASE)
            new_physics = re.findall(rf"{keyword}[^;,}}]*", new_code, re.IGNORECASE)

            if old_physics != new_physics:
                changes["physics_changes"].append(f"Modified {keyword} parameters")

        # Control changes
        control_keywords = ["keyboard", "mouse", "touch", "click", "keydown", "keyup"]
        for keyword in control_keywords:
            if (keyword in old_code) != (keyword in new_code):
                action = "Added" if keyword in new_code else "Removed"
                changes["control_changes"].append(f"{action} {keyword} controls")

        # Scoring changes
        score_patterns = [r"score\s*[+=]", r"points\s*[+=]", r"scoreText"]
        for pattern in score_patterns:
            old_score = bool(re.search(pattern, old_code, re.IGNORECASE))
            new_score = bool(re.search(pattern, new_code, re.IGNORECASE))

            if old_score != new_score:
                action = "Added" if new_score else "Removed"
                changes["scoring_changes"].append(f"{action} scoring system")

        # Visual changes
        visual_keywords = ["color", "size", "scale", "rotation", "opacity", "visible"]
        for keyword in visual_keywords:
            old_visual = len(re.findall(keyword, old_code, re.IGNORECASE))
            new_visual = len(re.findall(keyword, new_code, re.IGNORECASE))

            if abs(old_visual - new_visual) > 0:
                changes["visual_changes"].append(f"Modified {keyword} properties")

        # Audio changes
        audio_keywords = ["audio", "sound", "music", "play", "volume"]
        for keyword in audio_keywords:
            if (keyword in old_code.lower()) != (keyword in new_code.lower()):
                action = "Added" if keyword in new_code.lower() else "Removed"
                changes["audio_changes"].append(f"{action} {keyword} elements")

        return changes

    @staticmethod
    def calculate_change_impact(old_code: str, new_code: str) -> Dict[str, Any]:
        """
        Calculate the impact level of changes.

        Args:
            old_code: Original code
            new_code: Modified code

        Returns:
            Dictionary with impact analysis
        """
        # Calculate basic metrics
        old_size = len(old_code)
        new_size = len(new_code)
        size_change = abs(new_size - old_size) / max(old_size, 1)

        # Count significant elements
        old_functions = len(re.findall(r"function\s+\w+", old_code))
        new_functions = len(re.findall(r"function\s+\w+", new_code))
        function_change = abs(new_functions - old_functions)

        old_vars = len(re.findall(r"(?:var|let|const)\s+\w+", old_code))
        new_vars = len(re.findall(r"(?:var|let|const)\s+\w+", new_code))
        var_change = abs(new_vars - old_vars)

        # Determine impact level
        if size_change > 0.5 or function_change > 3 or var_change > 5:
            impact_level = "high"
        elif size_change > 0.2 or function_change > 1 or var_change > 2:
            impact_level = "medium"
        else:
            impact_level = "low"

        return {
            "impact_level": impact_level,
            "size_change_percent": round(size_change * 100, 2),
            "functions_changed": function_change,
            "variables_changed": var_change,
            "risk_factors": SemanticDiffAnalyzer._identify_risk_factors(old_code, new_code),
            "recommendations": SemanticDiffAnalyzer._generate_recommendations(impact_level),
        }

    @staticmethod
    def _identify_risk_factors(old_code: str, new_code: str) -> List[str]:
        """Identify potential risk factors in code changes."""
        risks = []

        # Check for removal of error handling
        old_try_catch = len(re.findall(r"try\s*{", old_code))
        new_try_catch = len(re.findall(r"try\s*{", new_code))

        if new_try_catch < old_try_catch:
            risks.append("Removed error handling code")

        # Check for performance risks
        old_loops = len(re.findall(r"\b(?:for|while)\b", old_code))
        new_loops = len(re.findall(r"\b(?:for|while)\b", new_code))

        if new_loops > old_loops * 2:
            risks.append("Significant increase in loop structures")

        # Check for security risks
        security_patterns = ["innerHTML", "eval", "document.write"]
        for pattern in security_patterns:
            if pattern not in old_code and pattern in new_code:
                risks.append(f"Added potentially unsafe code: {pattern}")

        return risks

    @staticmethod
    def _generate_recommendations(impact_level: str) -> List[str]:
        """Generate recommendations based on impact level."""
        recommendations = []

        if impact_level == "high":
            recommendations.extend(
                [
                    "Thoroughly test all game functionality",
                    "Verify performance hasn't degraded",
                    "Check for breaking changes",
                    "Consider code review",
                ]
            )
        elif impact_level == "medium":
            recommendations.extend(
                [
                    "Test modified features",
                    "Verify game still works as expected",
                    "Check for unintended side effects",
                ]
            )
        else:
            recommendations.extend(
                ["Basic functionality test recommended", "Changes appear minimal and safe"]
            )

        return recommendations
