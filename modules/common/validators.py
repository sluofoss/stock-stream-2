"""Data validation utilities for stock-stream-2."""

import math
import re
from datetime import date, datetime
from typing import Any

import polars as pl

from modules.common.exceptions import ValidationError


def validate_symbol(symbol: str) -> None:
    """Validate stock symbol format.

    Args:
        symbol: Stock symbol to validate

    Raises:
        ValidationError: If symbol format is invalid
    """
    if not symbol:
        raise ValidationError("Symbol cannot be empty")

    if not re.match(r"^[A-Z0-9]{1,5}$", symbol):
        raise ValidationError(
            f"Invalid symbol format: {symbol}. Must be 1-5 uppercase alphanumeric characters",
            details={"symbol": symbol},
        )


def validate_date(date_value: date | str) -> date:
    """Validate and parse date.

    Args:
        date_value: Date to validate (date object or ISO string)

    Returns:
        Validated date object

    Raises:
        ValidationError: If date is invalid
    """
    if isinstance(date_value, str):
        try:
            date_value = datetime.fromisoformat(date_value).date()
        except ValueError as e:
            raise ValidationError(
                f"Invalid date format: {date_value}. Expected ISO format YYYY-MM-DD",
                details={"date": date_value, "error": str(e)},
            )

    if date_value > date.today():
        raise ValidationError(
            f"Date cannot be in the future: {date_value}",
            details={"date": str(date_value)},
        )

    if date_value < date(1990, 1, 1):
        raise ValidationError(
            f"Date too far in the past: {date_value}",
            details={"date": str(date_value)},
        )

    return date_value


def validate_ohlcv_row(row: dict[str, Any]) -> list[str]:
    """Validate a single OHLCV data row.

    Args:
        row: Dictionary with OHLCV data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    required_fields = ["open", "high", "low", "close", "volume"]
    for field in required_fields:
        if field not in row:
            errors.append(f"Missing required field: {field}")
            return errors  # Can't continue validation without required fields

    # Check non-negative prices
    for field in ["open", "high", "low", "close"]:
        if row[field] <= 0:
            errors.append(f"{field} must be positive: {row[field]}")

    # Check volume is non-negative
    if row["volume"] < 0:
        errors.append(f"volume must be non-negative: {row['volume']}")

    # Check high/low relationships
    if row["high"] < row["low"]:
        errors.append(f"high ({row['high']}) must be >= low ({row['low']})")

    if row["high"] < row["open"]:
        errors.append(f"high ({row['high']}) must be >= open ({row['open']})")

    if row["high"] < row["close"]:
        errors.append(f"high ({row['high']}) must be >= close ({row['close']})")

    if row["low"] > row["open"]:
        errors.append(f"low ({row['low']}) must be <= open ({row['open']})")

    if row["low"] > row["close"]:
        errors.append(f"low ({row['low']}) must be <= close ({row['close']})")

    # Check for suspicious price changes (>50% in one day)
    if "open" in row and "close" in row:
        price_change = abs(row["close"] - row["open"]) / row["open"]
        if price_change > 0.5:
            errors.append(
                f"Suspicious price change >50%: open={row['open']}, close={row['close']}"
            )

    # Check for infinities and NaN
    for field in ["open", "high", "low", "close", "volume"]:
        value = row[field]
        if not math.isfinite(value):
            errors.append(f"{field} is not finite: {value}")

    return errors


def validate_dataframe(df: pl.DataFrame) -> list[str]:
    """Validate a DataFrame of stock data.

    Args:
        df: Polars DataFrame with stock data

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required columns
    required_columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
        return errors  # Can't continue without required columns

    # Check for empty DataFrame
    if df.height == 0:
        errors.append("DataFrame is empty")
        return errors

    # Check for duplicates
    duplicates = df.select(["symbol", "date"]).is_duplicated().sum()
    if duplicates > 0:
        errors.append(f"Found {duplicates} duplicate (symbol, date) pairs")

    # Validate each row
    for row in df.iter_rows(named=True):
        row_errors = validate_ohlcv_row(row)
        if row_errors:
            errors.extend([f"Row {row.get('symbol', 'unknown')} {row.get('date', 'unknown')}: {e}" for e in row_errors])

    return errors


def validate_config(config: dict[str, Any]) -> None:
    """Validate configuration dictionary.

    Args:
        config: Configuration dictionary

    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError("Configuration must be a dictionary")

    required_keys = ["symbols"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValidationError(
            f"Missing required configuration keys: {missing_keys}",
            details={"missing_keys": missing_keys},
        )

    if not isinstance(config["symbols"], list):
        raise ValidationError(
            "Configuration 'symbols' must be a list",
            details={"symbols_type": type(config["symbols"]).__name__},
        )

    if len(config["symbols"]) == 0:
        raise ValidationError("Configuration 'symbols' list is empty")

    # Validate each symbol
    for symbol in config["symbols"]:
        validate_symbol(symbol)
