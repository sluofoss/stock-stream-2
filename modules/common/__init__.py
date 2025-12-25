"""Common utilities for stock-stream-2.

This package provides shared functionality including exceptions,
validators, and logging configuration.

The logger is automatically configured when this package is imported.
"""

# Import logger module to trigger auto-configuration
from . import logger  # noqa: F401

# Export commonly used items
from .exceptions import (
    ConfigurationError,
    DataFetchError,
    DataQualityError,
    RateLimitError,
    StockStreamError,
    StorageError,
    ValidationError,
)
from .validators import (
    validate_config,
    validate_dataframe,
    validate_date,
    validate_ohlcv_row,
    validate_symbol,
)

__all__ = [
    # Exceptions
    "StockStreamError",
    "ConfigurationError",
    "ValidationError",
    "RateLimitError",
    "StorageError",
    "DataFetchError",
    "DataQualityError",
    # Validators
    "validate_symbol",
    "validate_date",
    "validate_ohlcv_row",
    "validate_dataframe",
    "validate_config",
]
