#!/usr/bin/env python3
"""
Simple script to run the CMBAgent backend server
"""

import logging
import uvicorn
import sys
from pathlib import Path

# Add the parent directory to the path to import cmbagent
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting CMBAgent Backend Server")
    logger.info("Server: http://localhost:8000 | WebSocket: ws://localhost:8000/ws/{task_id} | Docs: http://localhost:8000/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
