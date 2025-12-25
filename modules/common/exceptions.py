"""Custom exceptions for stock-stream-2 project."""

from typing import Any


class StockStreamError(Exception):
    """Base exception for all stock-stream errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(StockStreamError):
    """Raised when configuration is invalid or missing."""

    pass


class ValidationError(StockStreamError):
    """Raised when data validation fails."""

    pass


class RateLimitError(StockStreamError):
    """Raised when API rate limit is exceeded."""

    pass


class StorageError(StockStreamError):
    """Raised when S3 storage operations fail."""

    pass


class DataFetchError(StockStreamError):
    """Raised when data fetching from external source fails."""

    pass


class DataQualityError(StockStreamError):
    """Raised when data quality checks fail."""

    pass
