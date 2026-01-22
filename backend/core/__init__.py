"""
Core module for FastAPI application setup and configuration.
"""

from core.app import create_app, get_app
from core.config import settings, Settings

__all__ = [
    "create_app",
    "get_app",
    "settings",
    "Settings",
]
