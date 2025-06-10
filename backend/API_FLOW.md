# AI Game Generator - Core API Flow

This document describes the complete user journey for AI game generation using natural language prompts. The flow is designed for **core functionality only** - generating HTML5 games from text descriptions and modifying them through conversational AI.

## Overview

The AI Game Generator provides a streamlined experience:
- **Generate Games**: Create complete HTML5 games from natural language descriptions
- **Conversational Modifications**: Modify games through real-time chat
- **Session Management**: Maintain state and conversation history
- **Real-time Updates**: WebSocket support for live game updates

---

## Complete User Journey

### Step 1: Health Check (Optional)
```http
GET /api/health/
```

**Purpose**: Verify backend service availability

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

**When Used**: Frontend app initialization to ensure backend is available

---

### Step 2: Create Session
```http
POST /api/sessions/create
```

**Purpose**: Initialize a new game development session

**Request Body (Optional)**:
```json
{
  "user_id": "user_123",
  "initial_prompt": "Create a platformer game",
  "client_info": {
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1"
  },
  "preferences": {
    "preferred_engine": "phaser",
    "difficulty": "beginner"
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Session created successfully",
  "data": {
    "session_id": "session_abc123def",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "expires_at": "2024-01-15T11:30:00Z",
    "preferences": {
      "preferred_engine": "phaser",
      "difficulty": "beginner"
    },
    "metadata": {
      "created_by": "api",
      "initial_prompt": "Create a platformer game"
    }
  }
}
```

**Critical**: Save the `session_id` - required for all subsequent API calls

---

### Step 3: Generate Initial Game
```http
POST /api/games/generate
```

**Purpose**: Generate complete HTML5 game from natural language description

**Request Body**:
```json
{
  "prompt": "Create a blue platformer game where the player can jump on green platforms to reach a golden coin at the top. Add simple physics and arrow key controls.",
  "game_type": "platformer",
  "engine": "phaser",
  "difficulty": "beginner",
  "features": ["physics", "collision_detection"],
  "session_id": "session_abc123def"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Game created successfully",
  "data": {
    "session_id": "session_abc123def",
    "game_code": "<!DOCTYPE html>\n<html>\n<head>\n  <title>Platformer Game</title>\n  <script src=\"https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.min.js\"></script>\n</head>\n<body>\n  <script>\n    // Complete game code here...\n  </script>\n</body>\n</html>",
    "game_id": "game_xyz789",
    "game_type": "PLATFORMER",
    "engine": "phaser",
    "generation_time": 4.2,
    "tokens_used": 1250,
    "version": 1,
    "warnings": []
  }
}
```

**Result**: Complete, playable HTML5 game ready to run in browser

---

### Step 4: Get Current Session State
```http
GET /api/sessions/{session_id}
```

**Purpose**: Retrieve comprehensive session information including current game

**Response**:
```json
{
  "success": true,
  "message": "Session state retrieved successfully",
  "data": {
    "session_id": "session_abc123def",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "last_activity": "2024-01-15T10:34:00Z",
    "expires_at": "2024-01-15T11:30:00Z",
    "user_id": null,
    "current_game": {
      "game_id": "game_xyz789",
      "games": ["game_xyz789"],
      "generation_count": 1,
      "modifications_made": 0
    },
    "conversation": {
      "message_count": 0
    },
    "session_stats": {
      "duration": 240.5,
      "activity_level": "new"
    }
  }
}
```

---

### Step 5: Establish WebSocket Connection (Real-time)
```websocket
WS /api/chat/ws/{session_id}
```

**Purpose**: Enable real-time chat and live game updates

**Connection URL**:
```
ws://localhost:8000/api/chat/ws/session_abc123def
```

**Connection Flow**:
```javascript
// Client connects
const ws = new WebSocket('ws://localhost:8000/api/chat/ws/session_abc123def');

// Server sends confirmation
{
  "type": "connection",
  "data": {
    "message": "Connected to chat",
    "session_id": "session_abc123def"
  }
}

// Client sends modification request
{
  "type": "chat_message",
  "message": "Make the player red and increase jump height"
}

// Server responds with updated game
{
  "type": "chat_response",
  "data": {
    "response": "I've made the player red and increased jump height!",
    "game_updated": true,
    "modifications_applied": ["player_color_change", "jump_physics_adjustment"]
  }
}
```

---

### Step 6: Chat-Based Game Modifications
```http
POST /api/chat/message
```

**Purpose**: Modify games through natural language chat

**Request Body**:
```json
{
  "message": "Make the player red and increase jump height",
  "session_id": "session_abc123def"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Message processed successfully",
  "data": {
    "response": "I've updated your game! The player is now red and has increased jump height for better gameplay.",
    "intent": "modify_visual_and_gameplay",
    "modifications_applied": [
      "player_color_change",
      "jump_physics_adjustment"
    ],
    "game_updated": true,
    "updated_game_code": "<!DOCTYPE html>...",
    "processing_time": 2.1,
    "confidence": 0.95
  }
}
```

**Available Modification Types**:
- **Visual**: "Make the player red", "Change platform color to green"
- **Gameplay**: "Increase jump height", "Add more platforms", "Make it faster"
- **Features**: "Add sound effects", "Add enemies", "Add power-ups"
- **Physics**: "Reduce gravity", "Increase player speed"

---

### Step 7: Get Conversation History
```http
GET /api/chat/history/{session_id}?limit=50
```

**Purpose**: Retrieve conversation history for context

**Response**:
```json
{
  "success": true,
  "message": "Conversation history retrieved successfully",
  "data": {
    "session_id": "session_abc123def",
    "messages": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "Create a blue platformer game",
        "timestamp": "2024-01-15T10:30:00Z"
      },
      {
        "id": "msg_002", 
        "role": "assistant",
        "content": "I've created a blue platformer game with jumping mechanics and platforms.",
        "timestamp": "2024-01-15T10:30:08Z"
      },
      {
        "id": "msg_003",
        "role": "user", 
        "content": "Make the player red and increase jump height",
        "timestamp": "2024-01-15T10:35:00Z"
      },
      {
        "id": "msg_004",
        "role": "assistant",
        "content": "I've updated your game! The player is now red and has increased jump height.",
        "timestamp": "2024-01-15T10:35:03Z"
      }
    ],
    "total_messages": 4,
    "conversation_stats": {
      "modifications_made": 1,
      "avg_response_time": 2.5
    }
  }
}
```

---

### Step 8: Get Specific Game Information
```http
GET /api/games/info/{session_id}/{game_id}
```

**Purpose**: Retrieve detailed information about a specific game

**Response**:
```json
{
  "success": true,
  "message": "Game information retrieved successfully", 
  "data": {
    "game_id": "game_xyz789",
    "session_id": "session_abc123def",
    "created_at": "2024-01-15T10:30:08Z",
    "status": "active",
    "version": 1
  }
}
```

---

### Step 9: Reset Conversation (Optional)
```http
POST /api/chat/reset/{session_id}
```

**Purpose**: Clear conversation history while preserving game state

**Response**:
```json
{
  "success": true,
  "message": "Conversation reset successfully",
  "data": {
    "session_id": "session_abc123def",
    "conversation_cleared": true,
    "game_preserved": true,
    "reset_timestamp": "2024-01-15T11:00:00Z"
  }
}
```

---

### Step 10: Session Cleanup
```http
DELETE /api/sessions/{session_id}
```

**Purpose**: Clean up session when user is done

**Response**:
```json
{
  "success": true,
  "message": "Session cleaned up successfully",
  "data": {
    "session_id": "session_abc123def", 
    "cleaned_up": true
  }
}
```

---

## Complete Sequential Example

### Frontend Implementation Example
```javascript
class GameGenerator {
  constructor() {
    this.sessionId = null;
    this.ws = null;
  }

  // Step 1 & 2: Initialize session
  async initializeSession() {
    // Optional health check
    await fetch('/api/health/');
    
    // Create session
    const response = await fetch('/api/sessions/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'user_123',
        preferences: { preferred_engine: 'phaser' }
      })
    });
    
    const result = await response.json();
    this.sessionId = result.data.session_id;
  }

  // Step 3: Generate initial game
  async generateGame(prompt) {
    const response = await fetch('/api/games/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        game_type: 'platformer',
        engine: 'phaser',
        session_id: this.sessionId
      })
    });
    
    const result = await response.json();
    return result.data.game_code;
  }

  // Step 5: Connect WebSocket
  connectWebSocket() {
    this.ws = new WebSocket(`ws://localhost:8000/api/chat/ws/${this.sessionId}`);
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'chat_response') {
        this.updateGameDisplay(message.data.updated_game_code);
      }
    };
  }

  // Step 6: Send chat modifications
  async modifyGame(message) {
    const response = await fetch('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        session_id: this.sessionId
      })
    });
    
    const result = await response.json();
    return result.data;
  }

  // Step 10: Cleanup
  async cleanup() {
    if (this.ws) this.ws.close();
    
    await fetch(`/api/sessions/${this.sessionId}`, {
      method: 'DELETE'
    });
  }
}

// Usage
const generator = new GameGenerator();
await generator.initializeSession();
const gameCode = await generator.generateGame("Create a blue platformer game");
generator.connectWebSocket();
await generator.modifyGame("Make the player red");
```

---

## Error Handling

All endpoints return standardized error responses:

```json
{
  "success": false,
  "error": "Session not found",
  "error_code": "SESSION_NOT_FOUND",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Common Error Codes**:
- `SESSION_NOT_FOUND` - Invalid session ID
- `VALIDATION_ERROR` - Invalid request data
- `INTERNAL_ERROR` - Server error
- `RATE_LIMIT_EXCEEDED` - Too many requests

---

## Production Considerations

### Session Management
- Sessions auto-expire after 1 hour of inactivity
- Sessions auto-extend on each API call
- Maximum 10 sessions per IP address

### WebSocket Connections
- Automatic reconnection with exponential backoff
- Heartbeat messages every 30 seconds
- Graceful degradation to HTTP if WebSocket fails

### Rate Limiting
- 60 requests per minute per session
- 10 game generations per hour per session
- 100 chat messages per hour per session

### Game Generation Limits
- Maximum prompt length: 5000 characters
- Maximum game code size: 2MB
- Generation timeout: 30 seconds

This streamlined API flow focuses on **core functionality only** - generating games from natural language and modifying them through conversational AI. The journey is simple, fast, and production-ready. 