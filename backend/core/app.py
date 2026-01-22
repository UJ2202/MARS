"""
FastAPI application factory and configuration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings

# Global app instance
_app: FastAPI = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global _app

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
