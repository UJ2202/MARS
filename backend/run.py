#!/usr/bin/env python3
"""
Simple script to run the CMBAgent backend server
"""

import logging
import os
import uvicorn
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in parent directory
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

# Add the parent directory to the path to import cmbagent
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting CMBAgent Backend Server")
    logger.info("Server: http://localhost:8000 | WebSocket: ws://localhost:8000/ws/{task_id} | Docs: http://localhost:8000/docs")

    # Get log directory from environment or use default
    work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
    work_dir = os.path.expanduser(work_dir)
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Logs will be written to %s/backend.log", log_dir)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        log_config=None,  # Don't override app's logging configuration
    )
