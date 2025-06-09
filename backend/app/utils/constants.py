"""
Application-wide constants for AI Game Generator backend.
Contains enums, static values, and configuration constants.
"""

from enum import Enum
from typing import Dict, List, Set


class GameType(str, Enum):
    """Supported game types."""

    PLATFORMER = "platformer"
    SHOOTER = "shooter"
    PUZZLE = "puzzle"
    RACING = "racing"
    ARCADE = "arcade"
    RPG = "rpg"
    STRATEGY = "strategy"


class MessageType(str, Enum):
    """Chat message types."""

    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    GAME_UPDATE = "game_update"
    TYPING_INDICATOR = "typing"
    ERROR_MESSAGE = "error"
    SUGGESTION = "suggestion"
    SYSTEM_MESSAGE = "system"


class SessionStatus(str, Enum):
    """Session status values."""

    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class GenerationStatus(str, Enum):
    """Game generation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModificationType(str, Enum):
    """Types of game modifications."""

    VISUAL_CHANGE = "visual_change"
    GAMEPLAY_CHANGE = "gameplay_change"
    FEATURE_ADDITION = "feature_addition"
    BUG_FIX = "bug_fix"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    CONTENT_ADDITION = "content_addition"


class ValidationLevel(str, Enum):
    """Code validation levels."""

    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"


# HTTP Status Codes
HTTP_STATUS = {
    "OK": 200,
    "CREATED": 201,
    "ACCEPTED": 202,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "CONFLICT": 409,
    "UNPROCESSABLE_ENTITY": 422,
    "TOO_MANY_REQUESTS": 429,
    "INTERNAL_SERVER_ERROR": 500,
    "NOT_IMPLEMENTED": 501,
    "SERVICE_UNAVAILABLE": 503,
}

# Redis Key Prefixes
REDIS_KEYS = {
    "SESSION": "session:",
    "GAME_STATE": "game_state:",
    "CONVERSATION": "conversation:",
    "CONVERSATION_CONTEXT": "conversation_context:",
    "RATE_LIMIT": "rate_limit:",
    "TEMPLATE_CACHE": "template_cache:",
    "USER_SESSIONS": "user_sessions:",
    "GENERATION_LOCK": "generation_lock:",
    "WEBSOCKET_CONNECTIONS": "ws_connections:",
}

# Blocked Keywords for Security
BLOCKED_KEYWORDS = {
    "eval",
    "exec",
    "import os",
    "import sys",
    "subprocess",
    "shell",
    "cmd",
    "powershell",
    "bash",
    "sh",
    "__import__",
    "compile",
    "execfile",
    "input",
    "raw_input",
    "file",
    "open",
}

# OpenAI Model Configurations
OPENAI_MODELS = {
    "gpt-4-1106-preview": {
        "max_tokens": 4096,
        "supports_functions": True,
        "cost_per_1k_tokens": 0.03,
    },
    "gpt-4": {
        "max_tokens": 8192,
        "supports_functions": True,
        "cost_per_1k_tokens": 0.06,
    },
    "gpt-3.5-turbo-1106": {
        "max_tokens": 4096,
        "supports_functions": True,
        "cost_per_1k_tokens": 0.002,
    },
}

# Game Engine Libraries and Versions
GAME_ENGINES = {
    "phaser": {
        "version": "3.70.0",
        "cdn_url": "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.min.js",
        "supports_2d": True,
        "supports_3d": False,
    },
    "three": {
        "version": "0.158.0",
        "cdn_url": "https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js",
        "supports_2d": False,
        "supports_3d": True,
    },
    "p5": {
        "version": "1.7.0",
        "cdn_url": "https://cdn.jsdelivr.net/npm/p5@1.7.0/lib/p5.min.js",
        "supports_2d": True,
        "supports_3d": True,
    },
}

# Engine Type Constants for backwards compatibility
ENGINE_TYPES = {"phaser": "phaser", "three": "three", "p5": "p5", "canvas": "canvas"}

# Difficulty Levels
DIFFICULTY_LEVELS = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
    "expert": "expert",
}

# Template Configuration
TEMPLATE_CONFIG = {
    "max_size": 512 * 1024,  # 512KB
    "allowed_extensions": {".html", ".js", ".json"},
    "required_metadata": {"name", "description", "type", "difficulty"},
    "validation_timeout": 10,  # seconds
}

# Code Validation Rules
CODE_VALIDATION = {
    "blocked_patterns": [
        r"document\.write",
        r"eval\s*\(",
        r"Function\s*\(",
        r"setTimeout\s*\(",
        r"setInterval\s*\(",
        r"import\s+.*\s+from",
        r"require\s*\(",
        r"process\.",
        r"fs\.",
        r"path\.",
        r"crypto\.",
        r"Buffer\.",
    ],
    "required_patterns": [
        r"<!DOCTYPE html>",
        r"<html.*>",
        r"</html>",
        r"<script.*>.*</script>",
    ],
    "max_script_tags": 10,
    "max_inline_scripts": 5,
    "allowed_domains": {
        "cdn.jsdelivr.net",
        "cdnjs.cloudflare.com",
        "unpkg.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    },
}

# AI Prompt Templates
AI_PROMPTS = {
    "system_base": """You are an expert game developer AI assistant that creates and modifies HTML5 games.
You specialize in generating complete, playable games using modern web technologies like Phaser 3, Three.js, and HTML5 Canvas.

CORE PRINCIPLES:
1. Generate complete, self-contained HTML files that run immediately in a browser
2. Use CDN links for external libraries (no local file dependencies)
3. Include all necessary code (HTML, CSS, JavaScript) in a single file
4. Ensure games are playable, responsive, and well-structured
5. Follow web development best practices and security guidelines

MODIFICATION PRINCIPLES:
1. Make surgical, targeted changes to preserve existing functionality
2. Maintain code quality and game performance
3. Explain modifications clearly and suggest improvements
4. Respect user intentions while ensuring technical feasibility
""",
    "game_creation": """Create a {game_type} game based on this description: {description}

REQUIREMENTS:
- Single HTML file with embedded CSS and JavaScript
- Use {engine} game engine from CDN
- Include game controls and instructions
- Make it visually appealing and fun to play
- Ensure responsive design for different screen sizes

OUTPUT FORMAT:
Return only the complete HTML code, nothing else.""",
    "game_modification": """Modify the existing game according to this request: {modification_request}

CURRENT GAME CODE:
{current_code}

CONVERSATION CONTEXT:
{conversation_history}

REQUIREMENTS:
- Make only the requested changes
- Preserve all existing functionality unless explicitly asked to change it
- Maintain code structure and quality
- Ensure the game remains playable after modifications

OUTPUT FORMAT:
Return the complete modified HTML code.""",
    "default": """You are a helpful AI assistant for game development.""",
}

# Conversation Prompts
CONVERSATION_PROMPTS = {
    "welcome": "Welcome! I can help you create and modify HTML5 games. What would you like to build?",
    "game_ready": "Your game is ready! You can play it now or ask me to modify it.",
    "modification_complete": "I've updated your game as requested. Try it out!",
    "error_occurred": "I encountered an issue. Let me try a different approach.",
}

# Modification Prompts
MODIFICATION_PROMPTS = {
    "visual_change": "I'll make visual changes while preserving the game mechanics.",
    "gameplay_change": "I'll modify the gameplay while maintaining core functionality.",
    "feature_addition": "I'll add the requested feature to your game.",
    "bug_fix": "I'll identify and fix the issue you mentioned.",
}

# Default Game Templates
DEFAULT_TEMPLATES = {
    GameType.PLATFORMER: {
        "name": "Basic Platformer",
        "description": "A simple platformer with jumping mechanics",
        "features": ["player_character", "platforms", "gravity", "collision_detection"],
        "difficulty": "beginner",
        "game_type": GameType.PLATFORMER,
        "engine": "phaser",
        "tags": ["platformer", "jumping", "beginner"],
    },
    GameType.SHOOTER: {
        "name": "Space Shooter",
        "description": "A top-down space shooter game",
        "features": ["player_ship", "enemies", "projectiles", "score_system"],
        "difficulty": "intermediate",
        "game_type": GameType.SHOOTER,
        "engine": "phaser",
        "tags": ["shooter", "space", "intermediate"],
    },
    GameType.PUZZLE: {
        "name": "Match-3 Puzzle",
        "description": "A tile-matching puzzle game",
        "features": ["grid_system", "tile_matching", "score_tracking", "level_progression"],
        "difficulty": "intermediate",
        "game_type": GameType.PUZZLE,
        "engine": "phaser",
        "tags": ["puzzle", "matching", "intermediate"],
    },
}

# WebSocket Event Types
WS_EVENTS = {
    "CONNECTION": "connection",
    "DISCONNECTION": "disconnection",
    "MESSAGE": "message",
    "GAME_UPDATE": "game_update",
    "TYPING_START": "typing_start",
    "TYPING_STOP": "typing_stop",
    "ERROR": "error",
    "HEARTBEAT": "heartbeat",
    "SESSION_UPDATE": "session_update",
}

# Rate Limiting Windows
RATE_LIMIT_WINDOWS = {
    "message": 60,  # seconds
    "generation": 300,  # 5 minutes
    "session_creation": 3600,  # 1 hour
    "api_calls": 60,  # 1 minute
}

# Error Messages
ERROR_MESSAGES = {
    "INVALID_SESSION": "Session not found or expired",
    "RATE_LIMIT_EXCEEDED": "Rate limit exceeded. Please try again later",
    "INVALID_GAME_TYPE": "Unsupported game type",
    "GENERATION_FAILED": "Failed to generate game. Please try again",
    "INVALID_CODE": "Generated code failed validation",
    "SESSION_LIMIT_REACHED": "Maximum number of sessions reached",
    "OPENAI_ERROR": "AI service temporarily unavailable",
    "REDIS_ERROR": "Session storage service unavailable",
    "VALIDATION_ERROR": "Input validation failed",
    "TIMEOUT_ERROR": "Request timed out",
    "INTERNAL_ERROR": "Internal server error occurred",
}

# Success Messages
SUCCESS_MESSAGES = {
    "GAME_CREATED": "Game successfully created",
    "GAME_MODIFIED": "Game successfully modified",
    "SESSION_CREATED": "Session created successfully",
    "SESSION_UPDATED": "Session updated successfully",
    "TEMPLATE_LOADED": "Template loaded successfully",
    "CODE_VALIDATED": "Code validation passed",
}

# File Size Limits (in bytes)
FILE_LIMITS = {
    "max_game_size": 2 * 1024 * 1024,  # 2MB
    "max_template_size": 512 * 1024,  # 512KB
    "max_conversation_size": 1 * 1024 * 1024,  # 1MB
    "max_session_data": 5 * 1024 * 1024,  # 5MB
}

# Timeout Values (in seconds)
TIMEOUTS = {
    "openai_request": 30,
    "redis_operation": 5,
    "code_validation": 10,
    "template_processing": 15,
    "websocket_heartbeat": 30,
    "session_cleanup": 60,
}

# Logging Categories
LOG_CATEGORIES = {
    "AUTH": "authentication",
    "SESSION": "session_management",
    "GAME": "game_generation",
    "AI": "ai_interaction",
    "WEBSOCKET": "websocket_communication",
    "VALIDATION": "code_validation",
    "PERFORMANCE": "performance_monitoring",
    "ERROR": "error_handling",
}

# Content Security Policy
CSP_CONFIG = {
    "default-src": "'self'",
    "script-src": "'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com unpkg.com",
    "style-src": "'self' 'unsafe-inline' fonts.googleapis.com",
    "font-src": "'self' fonts.gstatic.com",
    "img-src": "'self' data: blob:",
    "connect-src": "'self' ws: wss:",
    "media-src": "'self' blob:",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}

# Game Feature Categories
GAME_FEATURES = {
    "CORE": ["player", "controls", "collision", "physics"],
    "VISUAL": ["sprites", "animations", "effects", "ui"],
    "AUDIO": ["sound_effects", "background_music", "audio_controls"],
    "GAMEPLAY": ["scoring", "levels", "powerups", "enemies"],
    "ADVANCED": ["multiplayer", "save_system", "achievements", "leaderboards"],
}

# Performance Metrics
PERFORMANCE_THRESHOLDS = {
    "generation_time": 30,  # seconds
    "response_time": 2,  # seconds
    "memory_usage": 512,  # MB
    "concurrent_users": 1000,
    "requests_per_minute": 10000,
}
