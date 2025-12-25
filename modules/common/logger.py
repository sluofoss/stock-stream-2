"""Structured logging utilities for stock-stream-2."""

import json
import logging
import sys
from datetime import datetime
from typing import Any

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Only add handler if logger doesn't have one
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_structured(
    logger: logging.Logger,
    level: str,
    message: str,
    **kwargs: Any,
) -> None:
    """Log a structured message with additional context.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **kwargs: Additional context to include in structured log
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "message": message,
        **kwargs,
    }

    log_method = getattr(logger, level.lower())
    log_method(json.dumps(log_data))


class StructuredLogger:
    """Logger wrapper for structured logging."""

    def __init__(self, name: str, level: str = "INFO") -> None:
        """Initialize structured logger.

        Args:
            name: Logger name
            level: Log level
        """
        self.logger = get_logger(name, level)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        log_structured(self.logger, "debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        log_structured(self.logger, "info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        log_structured(self.logger, "warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        log_structured(self.logger, "error", message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        log_structured(self.logger, "critical", message, **kwargs)
