"""Unit tests for validators module."""

import pytest
from datetime import date

from modules.common.exceptions import ValidationError
from modules.common.validators import (
    validate_symbol,
    validate_date,
    validate_ohlcv_row,
    validate_config,
)


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_symbols(self) -> None:
        """Test validation of valid symbols."""
        valid_symbols = ["BHP", "CBA", "NAB", "A", "WBC1"]
        for symbol in valid_symbols:
            validate_symbol(symbol)  # Should not raise

    def test_invalid_empty_symbol(self) -> None:
        """Test that empty symbol raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_symbol("")

    def test_invalid_lowercase_symbol(self) -> None:
        """Test that lowercase symbol raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid symbol format"):
            validate_symbol("bhp")

    def test_invalid_long_symbol(self) -> None:
        """Test that too-long symbol raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid symbol format"):
            validate_symbol("TOOLONG")

    def test_invalid_special_chars(self) -> None:
        """Test that symbols with special characters raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid symbol format"):
            validate_symbol("BHP-A")


class TestValidateDate:
    """Tests for date validation."""

    def test_valid_date_object(self) -> None:
        """Test validation of valid date object."""
        test_date = date(2024, 1, 1)
        result = validate_date(test_date)
        assert result == test_date

    def test_valid_date_string(self) -> None:
        """Test validation of valid date string."""
        result = validate_date("2024-01-01")
        assert result == date(2024, 1, 1)

    def test_invalid_date_string(self) -> None:
        """Test that invalid date string raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid date format"):
            validate_date("2024-13-01")  # Invalid month

    def test_future_date(self) -> None:
        """Test that future date raises ValidationError."""
        future_date = date(2030, 1, 1)
        with pytest.raises(ValidationError, match="cannot be in the future"):
            validate_date(future_date)

    def test_too_old_date(self) -> None:
        """Test that date before 1990 raises ValidationError."""
        old_date = date(1989, 1, 1)
        with pytest.raises(ValidationError, match="too far in the past"):
            validate_date(old_date)


class TestValidateOHLCVRow:
    """Tests for OHLCV row validation."""

    def test_valid_row(self) -> None:
        """Test validation of valid OHLCV row."""
        row = {
            "open": 50.0,
            "high": 52.0,
            "low": 49.0,
            "close": 51.0,
            "volume": 1000000,
        }
        errors = validate_ohlcv_row(row)
        assert len(errors) == 0

    def test_missing_fields(self) -> None:
        """Test that missing required fields are detected."""
        row = {"open": 50.0, "high": 52.0}  # Missing fields
        errors = validate_ohlcv_row(row)
        assert len(errors) > 0
        assert any("Missing required field" in error for error in errors)

    def test_negative_price(self) -> None:
        """Test that negative prices are detected."""
        row = {
            "open": -50.0,
            "high": 52.0,
            "low": 49.0,
            "close": 51.0,
            "volume": 1000000,
        }
        errors = validate_ohlcv_row(row)
        assert len(errors) > 0
        assert any("must be positive" in error for error in errors)

    def test_high_low_relationship(self) -> None:
        """Test that high < low is detected."""
        row = {
            "open": 50.0,
            "high": 48.0,  # Invalid: high < low
            "low": 49.0,
            "close": 50.0,
            "volume": 1000000,
        }
        errors = validate_ohlcv_row(row)
        assert len(errors) > 0
        assert any("high" in error and "low" in error for error in errors)

    def test_suspicious_price_change(self) -> None:
        """Test that suspicious price changes are detected."""
        row = {
            "open": 50.0,
            "high": 100.0,
            "low": 50.0,
            "close": 100.0,  # 100% change
            "volume": 1000000,
        }
        errors = validate_ohlcv_row(row)
        assert len(errors) > 0
        assert any("Suspicious price change" in error for error in errors)


class TestValidateConfig:
    """Tests for configuration validation."""

    def test_valid_config(self) -> None:
        """Test validation of valid configuration."""
        config = {"symbols": ["BHP", "CBA", "NAB"]}
        validate_config(config)  # Should not raise

    def test_missing_symbols_key(self) -> None:
        """Test that missing symbols key raises ValidationError."""
        config = {}
        with pytest.raises(ValidationError, match="Missing required configuration"):
            validate_config(config)

    def test_empty_symbols_list(self) -> None:
        """Test that empty symbols list raises ValidationError."""
        config = {"symbols": []}
        with pytest.raises(ValidationError, match="symbols' list is empty"):
            validate_config(config)

    def test_invalid_symbol_in_list(self) -> None:
        """Test that invalid symbol in list raises ValidationError."""
        config = {"symbols": ["BHP", "invalid-symbol", "CBA"]}
        with pytest.raises(ValidationError, match="Invalid symbol format"):
            validate_config(config)
