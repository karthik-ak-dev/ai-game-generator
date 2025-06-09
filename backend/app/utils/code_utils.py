"""
Code manipulation utilities for AI Game Generator.
Provides HTML/CSS/JavaScript parsing, modification, and optimization functions.
"""

import hashlib
import html
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import lxml.html
from bs4 import BeautifulSoup, Comment


class CodeParseError(Exception):
    """Error in code parsing."""

    pass


class HTMLParser:
    """HTML parsing and manipulation utilities."""

    @staticmethod
    def parse_html(html_content: str) -> BeautifulSoup:
        """
        Parse HTML content using BeautifulSoup.

        Args:
            html_content: HTML string to parse

        Returns:
            BeautifulSoup object
        """
        try:
            return BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            raise CodeParseError(f"Failed to parse HTML: {str(e)}")

    @staticmethod
    def extract_scripts(html_content: str) -> List[Dict[str, Any]]:
        """
        Extract all script tags and their content.

        Args:
            html_content: HTML content

        Returns:
            List of script tag information
        """
        soup = HTMLParser.parse_html(html_content)
        scripts = []

        for i, script in enumerate(soup.find_all("script")):
            script_info = {
                "index": i,
                "src": script.get("src"),
                "content": script.string or "",
                "attributes": dict(script.attrs),
                "type": script.get("type", "text/javascript"),
                "position": "head" if script.find_parent("head") else "body",
            }
            scripts.append(script_info)

        return scripts

    @staticmethod
    def extract_styles(html_content: str) -> List[Dict[str, Any]]:
        """
        Extract all style tags and their content.

        Args:
            html_content: HTML content

        Returns:
            List of style tag information
        """
        soup = HTMLParser.parse_html(html_content)
        styles = []

        for i, style in enumerate(soup.find_all("style")):
            style_info = {
                "index": i,
                "content": style.string or "",
                "attributes": dict(style.attrs),
                "type": style.get("type", "text/css"),
            }
            styles.append(style_info)

        return styles

    @staticmethod
    def extract_meta_tags(html_content: str) -> Dict[str, str]:
        """
        Extract meta tag information.

        Args:
            html_content: HTML content

        Returns:
            Dictionary of meta tag information
        """
        soup = HTMLParser.parse_html(html_content)
        meta_info = {}

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            meta_info["title"] = title_tag.string or ""

        # Extract meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                meta_info[name] = content

        return meta_info

    @staticmethod
    def replace_script_content(html_content: str, script_index: int, new_content: str) -> str:
        """
        Replace content of a specific script tag.

        Args:
            html_content: Original HTML content
            script_index: Index of script tag to replace
            new_content: New script content

        Returns:
            Modified HTML content
        """
        soup = HTMLParser.parse_html(html_content)
        scripts = soup.find_all("script")

        if 0 <= script_index < len(scripts):
            scripts[script_index].string = new_content

        return str(soup)

    @staticmethod
    def insert_script(html_content: str, script_content: str, position: str = "body") -> str:
        """
        Insert a new script tag into HTML.

        Args:
            html_content: Original HTML content
            script_content: JavaScript code to insert
            position: Where to insert ('head' or 'body')

        Returns:
            Modified HTML content
        """
        soup = HTMLParser.parse_html(html_content)

        # Create new script tag
        new_script = soup.new_tag("script", type="text/javascript")
        new_script.string = script_content

        # Insert into appropriate location
        if position == "head":
            head = soup.find("head")
            if head:
                head.append(new_script)
        else:
            body = soup.find("body")
            if body:
                body.append(new_script)

        return str(soup)


class JavaScriptParser:
    """JavaScript parsing and manipulation utilities."""

    @staticmethod
    def extract_functions(js_content: str) -> List[Dict[str, Any]]:
        """
        Extract function definitions from JavaScript code.

        Args:
            js_content: JavaScript code

        Returns:
            List of function information
        """
        functions = []

        # Pattern for function declarations
        function_pattern = r"function\s+(\w+)\s*\([^)]*\)\s*\{"
        matches = re.finditer(function_pattern, js_content)

        for match in matches:
            function_info = {
                "name": match.group(1),
                "start_pos": match.start(),
                "declaration": match.group(0),
            }
            functions.append(function_info)

        # Pattern for arrow functions and function expressions
        arrow_pattern = (
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>\s*\{|function\s*\([^)]*\)\s*\{)"
        )
        matches = re.finditer(arrow_pattern, js_content)

        for match in matches:
            function_info = {
                "name": match.group(1),
                "start_pos": match.start(),
                "declaration": match.group(0),
                "type": "expression",
            }
            functions.append(function_info)

        return functions

    @staticmethod
    def extract_variables(js_content: str) -> List[Dict[str, Any]]:
        """
        Extract variable declarations from JavaScript code.

        Args:
            js_content: JavaScript code

        Returns:
            List of variable information
        """
        variables = []

        # Pattern for variable declarations
        var_pattern = r"(?:const|let|var)\s+(\w+)(?:\s*=\s*([^;]+))?[;\n]"
        matches = re.finditer(var_pattern, js_content)

        for match in matches:
            var_info = {
                "name": match.group(1),
                "value": match.group(2) if match.group(2) else None,
                "declaration_type": match.group(0).split()[0],
                "start_pos": match.start(),
            }
            variables.append(var_info)

        return variables

    @staticmethod
    def find_phaser_config(js_content: str) -> Optional[Dict[str, Any]]:
        """
        Find and extract Phaser game configuration.

        Args:
            js_content: JavaScript code

        Returns:
            Phaser config dictionary if found
        """
        # Look for Phaser.Game constructor or config object
        patterns = [
            r"new\s+Phaser\.Game\s*\(\s*(\{[^}]+\})",
            r"(?:const|let|var)\s+config\s*=\s*(\{[^}]+\})",
            r"Phaser\.Game\s*\(\s*(\{[^}]+\})",
        ]

        for pattern in patterns:
            match = re.search(pattern, js_content, re.DOTALL)
            if match:
                config_str = match.group(1)
                try:
                    # Basic parsing - would need proper JS parser for complex cases
                    config_str = re.sub(r"(\w+):", r'"\1":', config_str)  # Quote keys
                    config_str = re.sub(r"'([^']*)'", r'"\1"', config_str)  # Convert single quotes
                    return json.loads(config_str)
                except:
                    return {"raw": config_str}

        return None

    @staticmethod
    def replace_color_values(js_content: str, color_mapping: Dict[str, str]) -> str:
        """
        Replace color values in JavaScript code.

        Args:
            js_content: JavaScript code
            color_mapping: Dictionary of old_color -> new_color

        Returns:
            Modified JavaScript code
        """
        modified_content = js_content

        for old_color, new_color in color_mapping.items():
            # Replace hex colors
            old_color = old_color.replace("#", r"\#")
            modified_content = re.sub(
                f"[\"']#{old_color}[\"']", f'"{new_color}"', modified_content, flags=re.IGNORECASE
            )

            # Replace color names
            modified_content = re.sub(
                f"[\"'](?i){old_color}[\"']", f'"{new_color}"', modified_content
            )

        return modified_content


class CSSParser:
    """CSS parsing and manipulation utilities."""

    @staticmethod
    def extract_rules(css_content: str) -> List[Dict[str, Any]]:
        """
        Extract CSS rules from stylesheet content.

        Args:
            css_content: CSS content

        Returns:
            List of CSS rule information
        """
        rules = []

        # Simple CSS rule pattern
        rule_pattern = r"([^{]+)\s*\{\s*([^}]+)\s*\}"
        matches = re.finditer(rule_pattern, css_content)

        for match in matches:
            selector = match.group(1).strip()
            properties_str = match.group(2).strip()

            # Parse properties
            properties = {}
            prop_pattern = r"([^:]+):\s*([^;]+);?"
            prop_matches = re.finditer(prop_pattern, properties_str)

            for prop_match in prop_matches:
                prop_name = prop_match.group(1).strip()
                prop_value = prop_match.group(2).strip()
                properties[prop_name] = prop_value

            rule_info = {
                "selector": selector,
                "properties": properties,
                "start_pos": match.start(),
                "end_pos": match.end(),
            }
            rules.append(rule_info)

        return rules

    @staticmethod
    def modify_property(css_content: str, selector: str, property_name: str, new_value: str) -> str:
        """
        Modify a CSS property value.

        Args:
            css_content: Original CSS content
            selector: CSS selector to target
            property_name: Property to modify
            new_value: New property value

        Returns:
            Modified CSS content
        """
        # Escape special regex characters in selector
        escaped_selector = re.escape(selector)

        # Pattern to find the rule and property
        rule_pattern = f"({escaped_selector}\\s*\\{{[^}}]*){property_name}\\s*:\\s*[^;]+;"
        replacement = f"\\1{property_name}: {new_value};"

        modified_css = re.sub(rule_pattern, replacement, css_content, flags=re.IGNORECASE)

        # If property wasn't found, add it to the rule
        if modified_css == css_content:
            rule_end_pattern = f"({escaped_selector}\\s*\\{{[^}}]*)(\\}})"
            rule_with_property = f"\\1    {property_name}: {new_value};\\n\\2"
            modified_css = re.sub(rule_end_pattern, rule_with_property, css_content)

        return modified_css


class CodeOptimizer:
    """Code optimization utilities."""

    @staticmethod
    def minify_css(css_content: str) -> str:
        """
        Minify CSS content.

        Args:
            css_content: CSS content to minify

        Returns:
            Minified CSS content
        """
        # Remove comments
        css_content = re.sub(r"/\*.*?\*/", "", css_content, flags=re.DOTALL)

        # Remove extra whitespace
        css_content = re.sub(r"\s+", " ", css_content)

        # Remove whitespace around certain characters
        css_content = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", css_content)

        # Remove trailing semicolons before closing braces
        css_content = re.sub(r";\s*}", "}", css_content)

        return css_content.strip()

    @staticmethod
    def minify_javascript(js_content: str) -> str:
        """
        Basic JavaScript minification.

        Args:
            js_content: JavaScript content to minify

        Returns:
            Minified JavaScript content
        """
        # Remove single-line comments (be careful with URLs)
        js_content = re.sub(r"(?<!:)//.*$", "", js_content, flags=re.MULTILINE)

        # Remove multi-line comments
        js_content = re.sub(r"/\*.*?\*/", "", js_content, flags=re.DOTALL)

        # Compress whitespace
        js_content = re.sub(r"\s+", " ", js_content)

        # Remove whitespace around operators and punctuation
        js_content = re.sub(r"\s*([{}();,=+\-*/])\s*", r"\1", js_content)

        return js_content.strip()

    @staticmethod
    def optimize_html(html_content: str) -> str:
        """
        Optimize HTML content.

        Args:
            html_content: HTML content to optimize

        Returns:
            Optimized HTML content
        """
        soup = HTMLParser.parse_html(html_content)

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Minify inline CSS
        for style in soup.find_all("style"):
            if style.string:
                style.string = CodeOptimizer.minify_css(style.string)

        # Minify inline JavaScript
        for script in soup.find_all("script"):
            if script.string and not script.get("src"):
                script.string = CodeOptimizer.minify_javascript(script.string)

        return str(soup)


class CodeAnalyzer:
    """Code analysis utilities."""

    @staticmethod
    def analyze_complexity(code: str, code_type: str = "html") -> Dict[str, Any]:
        """
        Analyze code complexity metrics.

        Args:
            code: Code content to analyze
            code_type: Type of code ('html', 'css', 'javascript')

        Returns:
            Dictionary of complexity metrics
        """
        metrics = {
            "size_bytes": len(code.encode("utf-8")),
            "lines": len(code.split("\n")),
            "complexity_score": 0,
        }

        if code_type == "html":
            soup = HTMLParser.parse_html(code)
            metrics.update(
                {
                    "elements": len(soup.find_all()),
                    "scripts": len(soup.find_all("script")),
                    "styles": len(soup.find_all("style")),
                    "images": len(soup.find_all("img")),
                    "links": len(soup.find_all("a")),
                }
            )

            # Calculate complexity score
            metrics["complexity_score"] = (
                metrics["elements"] * 0.1
                + metrics["scripts"] * 2
                + metrics["styles"] * 1
                + metrics["lines"] * 0.01
            )

        elif code_type == "javascript":
            functions = JavaScriptParser.extract_functions(code)
            variables = JavaScriptParser.extract_variables(code)

            metrics.update(
                {
                    "functions": len(functions),
                    "variables": len(variables),
                    "conditionals": len(re.findall(r"\bif\b|\belse\b|\bswitch\b", code)),
                    "loops": len(re.findall(r"\bfor\b|\bwhile\b|\bdo\b", code)),
                }
            )

            # Calculate complexity score
            metrics["complexity_score"] = (
                metrics["functions"] * 2
                + metrics["variables"] * 0.5
                + metrics["conditionals"] * 1.5
                + metrics["loops"] * 2
            )

        elif code_type == "css":
            rules = CSSParser.extract_rules(code)
            metrics.update({"rules": len(rules), "selectors": len(rules)})

            # Calculate complexity score
            metrics["complexity_score"] = metrics["rules"] * 0.5

        return metrics

    @staticmethod
    def extract_game_features(html_content: str) -> List[str]:
        """
        Analyze HTML/JS code to detect game features.

        Args:
            html_content: Complete HTML game code

        Returns:
            List of detected features
        """
        features = []
        content_lower = html_content.lower()

        # Feature detection patterns
        feature_patterns = {
            "player_movement": [r"player\.x", r"player\.y", r"velocity", r"move"],
            "collision_detection": [r"collision", r"intersect", r"overlap", r"bounds"],
            "scoring": [r"score", r"points", r"highscore"],
            "sound_effects": [r"audio", r"sound", r"music", r"play\("],
            "animations": [r"animation", r"sprite", r"tween", r"animate"],
            "particle_effects": [r"particle", r"emitter", r"explosion"],
            "power_ups": [r"powerup", r"power.up", r"bonus", r"pickup"],
            "enemies": [r"enemy", r"monster", r"bad.guy", r"opponent"],
            "levels": [r"level", r"stage", r"world", r"map"],
            "physics": [r"gravity", r"physics", r"velocity", r"acceleration"],
            "input_handling": [r"keyboard", r"mouse", r"touch", r"input"],
            "ui_elements": [r"button", r"menu", r"hud", r"interface"],
        }

        for feature_name, patterns in feature_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    features.append(feature_name)
                    break

        return list(set(features))  # Remove duplicates


class CodeGenerator:
    """Code generation utilities."""

    @staticmethod
    def generate_html_template(
        title: str = "Game", engine: str = "phaser", css_content: str = "", js_content: str = ""
    ) -> str:
        """
        Generate basic HTML template for games.

        Args:
            title: Game title
            engine: Game engine to include
            css_content: CSS content
            js_content: JavaScript content

        Returns:
            Complete HTML template
        """
        engine_urls = {
            "phaser": "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.min.js",
            "three": "https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js",
            "p5": "https://cdn.jsdelivr.net/npm/p5@1.7.0/lib/p5.min.js",
        }

        engine_url = engine_urls.get(engine, engine_urls["phaser"])

        template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
        {css_content}
    </style>
</head>
<body>
    <div id="game-container">
        <canvas id="game-canvas"></canvas>
    </div>
    
    <script src="{engine_url}"></script>
    <script>
        {js_content}
    </script>
</body>
</html>"""

        return template

    @staticmethod
    def generate_game_hash(game_code: str) -> str:
        """
        Generate a hash for game code to detect changes.

        Args:
            game_code: Complete game code

        Returns:
            SHA-256 hash of the code
        """
        return hashlib.sha256(game_code.encode("utf-8")).hexdigest()[:16]
