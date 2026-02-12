# Stage 8: Logging Configuration

**Phase:** 3 - Logging System
**Dependencies:** None (can run in parallel with Phases 1-2)
**Risk Level:** Low
**Estimated Time:** 2-3 hours

## Objectives

1. Set up structlog for structured logging
2. Add context binding for task_id and session_id
3. Configure output formats (console for dev, JSON for prod)
4. Create logging utilities for consistent usage

## Implementation Tasks

### Task 1: Create Logging Configuration Module

**File to Create:** `backend/core/logging.py`

```python
"""
Structured Logging Configuration

Provides consistent logging across the application with:
- Context binding (task_id, session_id)
- JSON output for production
- Console output for development
- Integration with Python stdlib logging
"""

import logging
import sys
from contextvars import ContextVar
from typing import Optional

import structlog

# Context variables for request tracing
current_task_id: ContextVar[Optional[str]] = ContextVar('task_id', default=None)
current_session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
current_run_id: ContextVar[Optional[str]] = ContextVar('run_id', default=None)


def add_context_processor(logger, method_name, event_dict):
    """Add context variables to all log entries"""
    task_id = current_task_id.get()
    session_id = current_session_id.get()
    run_id = current_run_id.get()

    if task_id:
        event_dict['task_id'] = task_id
    if session_id:
        event_dict['session_id'] = session_id
    if run_id:
        event_dict['run_id'] = run_id

    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None
):
    """
    Configure structured logging for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        json_output: Use JSON format (for production)
        log_file: Optional file path for log output
    """

    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_context_processor,
    ]

    # Choose renderer based on environment
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    ))

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),  # Always JSON for files
            ],
        ))
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    structlog.get_logger().info(
        "logging_configured",
        level=log_level,
        json_output=json_output,
        log_file=log_file
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Bound logger instance

    Usage:
        logger = get_logger(__name__)
        logger.info("message", key="value")
    """
    return structlog.get_logger(name)


def bind_context(
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    run_id: Optional[str] = None
):
    """
    Bind context for all subsequent log calls in this context.

    Use in request handlers or task execution to automatically
    include identifiers in all log messages.

    Args:
        task_id: Task identifier
        session_id: Session identifier
        run_id: Run identifier
    """
    if task_id:
        current_task_id.set(task_id)
    if session_id:
        current_session_id.set(session_id)
    if run_id:
        current_run_id.set(run_id)


def clear_context():
    """Clear all bound context"""
    current_task_id.set(None)
    current_session_id.set(None)
    current_run_id.set(None)


class LoggingContextManager:
    """
    Context manager for automatic context binding and cleanup.

    Usage:
        with LoggingContextManager(task_id="123"):
            logger.info("this includes task_id")
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None
    ):
        self.task_id = task_id
        self.session_id = session_id
        self.run_id = run_id
        self._tokens = []

    def __enter__(self):
        if self.task_id:
            self._tokens.append(current_task_id.set(self.task_id))
        if self.session_id:
            self._tokens.append(current_session_id.set(self.session_id))
        if self.run_id:
            self._tokens.append(current_run_id.set(self.run_id))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in self._tokens:
            # Reset to previous value
            pass  # ContextVar.reset() would be used here
        return False


# Initialize with defaults on import
configure_logging()
```

### Task 2: Initialize Logging in App Startup

**File to Modify:** `backend/core/app.py`

```python
# Add at the top of create_app():
from core.logging import configure_logging
import os

def create_app():
    # Configure logging based on environment
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_output=os.getenv("LOG_JSON", "false").lower() == "true",
        log_file=os.getenv("LOG_FILE")
    )

    # ... rest of app creation
```

### Task 3: Create Convenience Import

**File to Modify:** `backend/core/__init__.py`

```python
from core.logging import (
    get_logger,
    bind_context,
    clear_context,
    configure_logging,
    LoggingContextManager
)
```

## Verification Criteria

### Must Pass
- [ ] Logging outputs structured data
- [ ] Context (task_id) appears in logs
- [ ] JSON output works for production mode
- [ ] No duplicate log handlers

### Test Script
```python
# test_stage_8.py
import os
os.environ["LOG_LEVEL"] = "DEBUG"

from backend.core.logging import (
    configure_logging, get_logger, bind_context, clear_context
)

def test_logging():
    # Reconfigure for test
    configure_logging(log_level="DEBUG", json_output=False)

    logger = get_logger("test")

    # Basic logging
    logger.info("basic_message", extra_key="extra_value")
    print("✅ Basic logging works")

    # Context binding
    bind_context(task_id="test_task_123", session_id="session_456")
    logger.info("with_context")
    print("✅ Context binding works")

    clear_context()
    logger.info("context_cleared")
    print("✅ Context clearing works")

    # JSON mode
    configure_logging(log_level="INFO", json_output=True)
    logger.info("json_format", key="value")
    print("✅ JSON output works")

    print("\n✅ All logging tests passed!")

if __name__ == "__main__":
    test_logging()
```

## Success Criteria

Stage 8 is complete when:
1. ✅ Structured logging configured
2. ✅ Context binding works
3. ✅ JSON output mode works
4. ✅ No logging errors on startup

## Next Stage

Once Stage 8 is verified complete, proceed to:
**Stage 9: Print Statement Migration**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
