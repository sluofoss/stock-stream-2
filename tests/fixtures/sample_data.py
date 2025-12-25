"""Fixtures for stock data testing."""

from datetime import date

import polars as pl
import pytest


@pytest.fixture
def sample_ohlcv_data() -> list[dict]:
    """Sample OHLCV data for testing."""
    return [
        {
            "symbol": "BHP",
            "date": date(2024, 12, 25),
            "open": 50.0,
            "high": 52.0,
            "low": 49.0,
            "close": 51.0,
            "volume": 1000000,
            "adjusted_close": 51.0,
        },
        {
            "symbol": "CBA",
            "date": date(2024, 12, 25),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 2000000,
            "adjusted_close": 101.0,
        },
        {
            "symbol": "NAB",
            "date": date(2024, 12, 25),
            "open": 30.0,
            "high": 31.0,
            "low": 29.5,
            "close": 30.5,
            "volume": 1500000,
            "adjusted_close": 30.5,
        },
    ]


@pytest.fixture
def sample_dataframe(sample_ohlcv_data: list[dict]) -> pl.DataFrame:
    """Sample DataFrame for testing."""
    return pl.DataFrame(sample_ohlcv_data)


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "symbols": ["BHP", "CBA", "NAB", "WBC", "ANZ"],
        "market": "ASX",
        "updated_at": "2024-12-25T00:00:00Z",
    }
