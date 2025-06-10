"""
Main FastAPI application for AI Game Generator backend.
Entry point with full application setup and configuration.
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .models.response_models import (
    ErrorDetail,
    create_error_response,
    create_validation_error_response,
)
from .routers.chat_router import router as chat_router
from .routers.game_router import router as game_router
from .routers.health_router import router as health_router
from .routers.session_router import router as session_router
from .utils.constants import HTTP_STATUS


# Configure structured logging
def configure_logging():
    """Configure structured logging with appropriate level and format."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            (
                structlog.processors.JSONRenderer()
                if settings.monitoring.structured_logging
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.app.log_level.upper()),
    )


# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger = structlog.get_logger(__name__)

    # Startup
    logger.info(
        "Starting AI Game Generator backend",
        version=settings.app.app_version,
        environment=settings.app.environment,
    )

    startup_success = True

    try:
        # Initialize Redis connection
        logger.info("Initializing Redis connection...")
        redis_connected = await _initialize_redis()
        if not redis_connected:
            logger.warning("Redis connection failed - session persistence will be limited")

        # Validate OpenAI configuration
        logger.info("Validating OpenAI configuration...")
        openai_valid = await _validate_openai_config()
        if not openai_valid:
            logger.warning("OpenAI configuration invalid - AI features will not work")
            if settings.is_production:
                logger.error("OpenAI is required in production")
                startup_success = False

        # Set startup time for metrics
        app.state.startup_time = time.time()
        app.state.redis_connected = redis_connected
        app.state.openai_configured = openai_valid

        if startup_success:
            logger.info("Application startup completed successfully")
        else:
            logger.error("Application startup completed with critical errors")
            if settings.is_production:
                raise RuntimeError("Critical services unavailable in production")

    except Exception as e:
        logger.error("Failed to initialize application", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down AI Game Generator backend")

    try:
        # Cleanup Redis connection
        from .services.redis_service import redis_service

        if redis_service.is_connected:
            await redis_service.disconnect()
            logger.info("Redis connection closed")

        logger.info("Shutdown completed successfully")

    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


async def _initialize_redis() -> bool:
    """Initialize Redis connection with retry logic."""
    logger = structlog.get_logger(__name__)

    try:
        from .services.redis_service import redis_service

        # Try to connect with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                connected = await redis_service.connect()
                if connected:
                    logger.info("Redis connection established successfully")
                    return True
                else:
                    logger.warning(f"Redis connection attempt {attempt + 1} failed")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                logger.warning(f"Redis connection attempt {attempt + 1} error", error=str(e))
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error("All Redis connection attempts failed")
        return False

    except Exception as e:
        logger.error("Redis initialization failed", error=str(e))
        return False


async def _validate_openai_config() -> bool:
    """Validate OpenAI configuration."""
    logger = structlog.get_logger(__name__)

    try:
        if not settings.openai.api_key or settings.openai.api_key == "your-openai-api-key-here":
            logger.error("OpenAI API key not configured")
            return False

        if len(settings.openai.api_key) < 10:
            logger.error("OpenAI API key appears invalid")
            return False

        logger.info(
            "OpenAI configuration validated",
            model=settings.openai.model,
            max_tokens=settings.openai.max_tokens,
        )
        return True

    except Exception as e:
        logger.error("OpenAI configuration validation failed", error=str(e))
        return False


# Create FastAPI application
def create_application() -> FastAPI:
    """Create and configure FastAPI application."""

    # Configure logging first
    configure_logging()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app.app_name,
        version=settings.app.app_version,
        description="AI-powered game generator with conversational interface",
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
        openapi_url="/openapi.json" if settings.app.debug else None,
        lifespan=lifespan,
    )

    # Add middleware
    setup_middleware(app)

    # Add exception handlers
    setup_exception_handlers(app)

    # Add request/response middleware for logging
    setup_request_logging(app)

    # Include routers
    setup_routers(app)

    return app


def setup_middleware(app: FastAPI):
    """Configure application middleware."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=settings.cors.credentials,
        allow_methods=settings.cors.methods,
        allow_headers=settings.cors.headers,
    )

    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        if settings.is_production:
            csp_parts = []
            for directive, sources in {
                "default-src": ["'self'"],
                "script-src": [
                    "'self'",
                    "'unsafe-inline'",
                    "cdn.jsdelivr.net",
                    "cdnjs.cloudflare.com",
                ],
                "style-src": ["'self'", "'unsafe-inline'", "fonts.googleapis.com"],
                "font-src": ["'self'", "fonts.gstatic.com"],
                "img-src": ["'self'", "data:", "blob:"],
                "connect-src": ["'self'"],
                "media-src": ["'self'", "blob:"],
                "object-src": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"],
            }.items():
                csp_parts.append(f"{directive} {' '.join(sources)}")

            response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        return response


def setup_exception_handlers(app: FastAPI):
    """Configure global exception handlers."""
    logger = structlog.get_logger(__name__)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(
            "HTTP exception occurred",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                message=exc.detail, error_code="HTTP_ERROR", status_code=exc.status_code
            ).dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Validation error occurred", errors=exc.errors(), path=request.url.path)

        # Format validation errors
        validation_errors = []
        for error in exc.errors():
            validation_errors.append(
                ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=error.get("msg", "Validation failed"),
                    field=".".join(str(loc) for loc in error.get("loc", [])),
                    details={"type": error.get("type"), "input": error.get("input")},
                )
            )

        response = create_validation_error_response(
            message="Request validation failed",
            validation_errors=validation_errors,
        )

        return JSONResponse(
            status_code=HTTP_STATUS["UNPROCESSABLE_ENTITY"], content=response.dict()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception occurred",
            error=str(exc),
            exception_type=type(exc).__name__,
            path=request.url.path,
            exc_info=True,
        )

        # Don't expose internal errors in production
        if settings.is_production:
            error_message = "Internal server error"
            error_details = None
        else:
            error_message = str(exc)
            error_details = {"type": type(exc).__name__}

        return JSONResponse(
            status_code=HTTP_STATUS["INTERNAL_SERVER_ERROR"],
            content=create_error_response(
                message=error_message,
                error_code="INTERNAL_ERROR",
                status_code=HTTP_STATUS["INTERNAL_SERVER_ERROR"],
                details=error_details,
            ).dict(),
        )


def setup_request_logging(app: FastAPI):
    """Setup request/response logging middleware."""
    logger = structlog.get_logger(__name__)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=round(process_time, 4),
        )

        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)

        return response


def setup_routers(app: FastAPI):
    """Setup and include API routers."""

    # Import and include routers
    try:
        app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])

        # Game generation and management
        app.include_router(game_router, prefix="/api/v1/games", tags=["Games"])

        # Conversational interface
        app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])

        # Session management
        app.include_router(session_router, prefix="/api/v1/sessions", tags=["Sessions"])

        logger = structlog.get_logger(__name__)
        logger.info(
            "All routers loaded successfully",
            routers=["health", "games", "chat", "sessions"],
        )

    except ImportError as e:
        logger = structlog.get_logger(__name__)
        logger.error("Failed to import routers", error=str(e))
        raise


# Create the app instance
app = create_application()


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with basic API information."""
    return {
        "name": settings.app.app_name,
        "version": settings.app.app_version,
        "environment": settings.app.environment,
        "status": "running",
        "docs_url": "/docs" if settings.app.debug else None,
    }


# Main entry point for running with uvicorn
def main():
    """Main entry point for running the application."""
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.reload and settings.app.debug,
        workers=settings.app.workers if not settings.app.debug else 1,
        log_level=settings.app.log_level.lower(),
        access_log=True,
        server_header=False,
        date_header=False,
    )


if __name__ == "__main__":
    main()
