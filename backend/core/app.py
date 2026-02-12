"""
FastAPI application factory and configuration.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging

# Global app instance
_app: FastAPI = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global _app

    # Configure structured logging based on environment
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_output=os.getenv("LOG_JSON", "false").lower() == "true",
        log_file=os.getenv("LOG_FILE")
    )

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _app = app
    return app


def get_app() -> FastAPI:
    """Get the current FastAPI application instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app
