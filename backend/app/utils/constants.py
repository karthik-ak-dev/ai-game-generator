"""
Core constants for AI Game Generator.
Essential constants for production functionality.
"""

from enum import Enum


class GameType(str, Enum):
    """Supported game types."""

    PLATFORMER = "platformer"
    SHOOTER = "shooter"
    PUZZLE = "puzzle"
    RACING = "racing"
    ARCADE = "arcade"
    RPG = "rpg"


class MessageType(str, Enum):
    """Chat message types."""

    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    GAME_UPDATE = "game_update"
    ERROR_MESSAGE = "error"


class SessionStatus(str, Enum):
    """Session status values."""

    ACTIVE = "active"


class GenerationStatus(str, Enum):
    """Game generation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Success Messages
SUCCESS_MESSAGES = {
    "SESSION_CREATED": "Session created successfully",
    "SESSION_TERMINATED": "Session terminated successfully",
    "GAME_GENERATED": "Game generated successfully",
}

# Error Messages
ERROR_MESSAGES = {
    "INTERNAL_ERROR": "An internal server error occurred",
    "SESSION_NOT_FOUND": "Session not found",
    "SESSION_EXPIRED": "Session has expired",
    "INVALID_SESSION": "Invalid session ID",
    "VALIDATION_FAILED": "Input validation failed",
    "UNAUTHORIZED": "Unauthorized access",
    "RATE_LIMIT_EXCEEDED": "Rate limit exceeded",
    "SERVICE_UNAVAILABLE": "Service temporarily unavailable",
}

# Redis Key Prefixes
REDIS_KEYS = {
    "SESSION": "session:",
    "GAME_STATE": "game_state:",
    "CONVERSATION": "conversation:",
    "CONVERSATION_CONTEXT": "conversation_context:",
}

# Game Engine Libraries
GAME_ENGINES = {
    "phaser": {
        "version": "3.70.0",
        "cdn_url": ("https://cdn.jsdelivr.net/npm/phaser@3.70.0/" "dist/phaser.min.js"),
    },
    "three": {
        "version": "0.158.0",
        "cdn_url": ("https://cdn.jsdelivr.net/npm/three@0.158.0/" "build/three.min.js"),
    },
    "p5": {
        "version": "1.7.0",
        "cdn_url": "https://cdn.jsdelivr.net/npm/p5@1.7.0/lib/p5.min.js",
    },
}

# AI Prompt Templates
AI_PROMPTS = {
    "system_base": (
        "You are an expert game developer AI assistant that creates "
        "and modifies HTML5 games.\n"
        "You generate complete, playable games using modern web technologies "
        "like Phaser 3, Three.js, and HTML5 Canvas.\n\n"
        "CORE PRINCIPLES:\n"
        "1. Generate complete, self-contained HTML files that run immediately in a browser\n"
        "2. Use CDN links for external libraries (no local file dependencies)\n"
        "3. Include all necessary code (HTML, CSS, JavaScript) in a single file\n"
        "4. Ensure games are playable, responsive, and well-structured\n\n"
        "OUTPUT FORMAT:\n"
        "Return only the complete HTML code, nothing else."
    ),
    "game_creation": (
        "Create a {game_type} game based on this description: {description}\n\n"
        "REQUIREMENTS:\n"
        "- Single HTML file with embedded CSS and JavaScript\n"
        "- Use {engine} game engine from CDN\n"
        "- Include game controls and instructions\n"
        "- Make it visually appealing and fun to play\n\n"
        "OUTPUT FORMAT:\n"
        "Return only the complete HTML code, nothing else."
    ),
    "game_modification": (
        "Modify the existing game according to this request:\n"
        "{modification_request}\n\n"
        "CURRENT GAME CODE:\n"
        "{current_code}\n\n"
        "REQUIREMENTS:\n"
        "- Make only the requested changes\n"
        "- Preserve all existing functionality unless explicitly asked to change it\n"
        "- Ensure the game remains playable after modifications\n\n"
        "OUTPUT FORMAT:\n"
        "Return the complete modified HTML code."
    ),
}

# Basic configuration
MAX_GAME_SIZE = 2 * 1024 * 1024  # 2MB
MAX_CONVERSATION_SIZE = 1 * 1024 * 1024  # 1MB
SESSION_TIMEOUT = 3600  # 1 hour
AI_REQUEST_TIMEOUT = 30
