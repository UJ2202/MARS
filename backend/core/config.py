"""
Configuration settings for the CMBAgent backend.
"""

import os
from typing import List
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Application settings with sensible defaults."""

    # App metadata
    app_title: str = "CMBAgent API"
    app_version: str = "1.0.0"

    # CORS settings
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
    ])

    # Default work directory
    default_work_dir: str = "~/Desktop/cmbdir"

    # File size limits
    max_file_size_mb: int = 10

    # Debug settings
    debug: bool = False

    def __post_init__(self):
        """Load settings from environment variables if available."""
        self.app_title = os.getenv("CMBAGENT_APP_TITLE", self.app_title)
        self.app_version = os.getenv("CMBAGENT_APP_VERSION", self.app_version)
        self.default_work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", self.default_work_dir)
        self.max_file_size_mb = int(os.getenv("CMBAGENT_MAX_FILE_SIZE_MB", str(self.max_file_size_mb)))
        self.debug = os.getenv("CMBAGENT_DEBUG", "false").lower() == "true"


# Global settings instance
settings = Settings()
