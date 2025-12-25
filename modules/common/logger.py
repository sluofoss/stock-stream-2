"""Logging configuration using loguru for the stock-stream-2 project.

This module configures loguru for AWS Lambda and local development.
Just import logger from loguru in your modules and use it directly.

Example:
    from loguru import logger
    
    # Simple logging
    logger.info("Processing symbol", symbol="BHP")
    
    # With structured data
    logger.bind(symbol="CBA", rows=1000).info("Data fetched")
    
    # Exception logging
    try:
        ...
    except Exception as e:
        logger.exception("Failed to fetch data")
"""

import os
import sys

from loguru import logger


def configure_logger(
    level: str = "INFO",
    serialize: bool = False,
) -> None:
    """Configure loguru logger for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        serialize: If True, serialize entire log record as JSON (for CloudWatch)
    """
    # Remove default handler
    logger.remove()
    
    if serialize:
        # JSON format for CloudWatch (full serialization)
        logger.add(
            sys.stderr,
            format="{message}",
            level=level,
            serialize=True,
            colorize=False,
        )
    else:
        # Human-readable format for local development
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True,
        )


# Auto-configure based on environment
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    # Lambda: JSON format for CloudWatch
    configure_logger(
        level=os.getenv("LOG_LEVEL", "INFO"),
        serialize=True,
    )
else:
    # Local: Human-readable colored output
    configure_logger(
        level=os.getenv("LOG_LEVEL", "INFO"),
        serialize=False,
    )
