"""Unit tests for the YahooFinanceFetcher class."""

from datetime import date, timedelta
from unittest.mock import MagicMock, Mock, patch

import polars as pl
import pytest
import yfinance as yf

from modules.common.exceptions import DataFetchError, RateLimitError
from modules.stock_data_fetcher.fetcher import YahooFinanceFetcher


class TestYahooFinanceFetcher:
    """Tests for YahooFinanceFetcher class."""

    @pytest.fixture
    def fetcher(self) -> YahooFinanceFetcher:
        """Create a YahooFinanceFetcher instance for testing."""
        return YahooFinanceFetcher(rate_limit_delay=0.1, max_retries=2, timeout=60)

    @pytest.fixture
    def mock_ticker_data(self) -> pl.DataFrame:
        """Create mock ticker data."""
        dates = [date(2024, 12, 24), date(2024, 12, 25), date(2024, 12, 26)]
        return pl.DataFrame(
            {
                "Date": dates,
                "Open": [50.0, 51.0, 52.0],
                "High": [52.0, 53.0, 54.0],
                "Low": [49.0, 50.0, 51.0],
                "Close": [51.0, 52.0, 53.0],
                "Volume": [1000000, 1100000, 1200000],
                "Adj Close": [51.0, 52.0, 53.0],
            }
        )

    def test_initialization(self, fetcher: YahooFinanceFetcher) -> None:
        """Test fetcher initialization."""
        assert fetcher.rate_limit_delay == 0.1
        assert fetcher.max_retries == 2
        assert fetcher.timeout == 60

    @patch("yfinance.Ticker")
    def test_fetch_single_symbol_success(
        self, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher, mock_ticker_data: pl.DataFrame
    ) -> None:
        """Test successful single symbol fetch."""
        # Setup mock
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_ticker_data.to_pandas()
        mock_ticker_class.return_value = mock_ticker

        # Test
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        result = fetcher.fetch_single_symbol("BHP", start_date, end_date)

        # Verify
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 3
        assert "symbol" in result.columns
        assert all(result["symbol"] == "BHP")
        mock_ticker_class.assert_called_once_with("BHP.AX")

    @patch("yfinance.Ticker")
    def test_fetch_single_symbol_with_retry(
        self, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher, mock_ticker_data: pl.DataFrame
    ) -> None:
        """Test fetch with retry on failure."""
        # Setup mock to fail first, then succeed
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = [
            Exception("Network error"),
            mock_ticker_data.to_pandas(),
        ]
        mock_ticker_class.return_value = mock_ticker

        # Test
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        result = fetcher.fetch_single_symbol("BHP", start_date, end_date)

        # Verify retry happened
        assert isinstance(result, pl.DataFrame)
        assert mock_ticker.history.call_count == 2

    @patch("yfinance.Ticker")
    def test_fetch_single_symbol_rate_limit(self, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher) -> None:
        """Test rate limit error handling."""
        # Setup mock to raise rate limit error
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("429 Too Many Requests")
        mock_ticker_class.return_value = mock_ticker

        # Test
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        with pytest.raises(RateLimitError):
            fetcher.fetch_single_symbol("BHP", start_date, end_date)

    @patch("yfinance.Ticker")
    def test_fetch_single_symbol_max_retries_exceeded(
        self, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher
    ) -> None:
        """Test that max retries raises DataFetchError."""
        # Setup mock to always fail
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mock_ticker_class.return_value = mock_ticker

        # Test
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        with pytest.raises(DataFetchError):
            fetcher.fetch_single_symbol("BHP", start_date, end_date)

        # Verify max retries
        assert mock_ticker.history.call_count == fetcher.max_retries + 1

    @patch("yfinance.Ticker")
    def test_fetch_single_symbol_empty_data(
        self, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher
    ) -> None:
        """Test handling of empty data response."""
        # Setup mock to return empty DataFrame
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pl.DataFrame().to_pandas()
        mock_ticker_class.return_value = mock_ticker

        # Test
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        with pytest.raises(DataFetchError, match="No data returned"):
            fetcher.fetch_single_symbol("BHP", start_date, end_date)

    @patch("yfinance.Ticker")
    @patch("time.sleep", return_value=None)  # Skip actual sleep
    def test_fetch_multiple_symbols(
        self, mock_sleep: Mock, mock_ticker_class: Mock, fetcher: YahooFinanceFetcher, mock_ticker_data: pl.DataFrame
    ) -> None:
        """Test fetching multiple symbols with rate limiting."""
        # Setup mock
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_ticker_data.to_pandas()
        mock_ticker_class.return_value = mock_ticker

        # Test
        symbols = ["BHP", "CBA", "NAB"]
        start_date = date(2024, 12, 24)
        end_date = date(2024, 12, 26)
        result = fetcher.fetch_multiple_symbols(symbols, start_date, end_date)

        # Verify
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 9  # 3 symbols * 3 days
        assert set(result["symbol"].unique()) == set(symbols)
        
        # Verify rate limiting (sleep called between symbols)
        assert mock_sleep.call_count == 2  # n-1 for n symbols

    def test_get_stats(self, fetcher: YahooFinanceFetcher) -> None:
        """Test getting fetcher statistics."""
        # Make some mock calls to increment counters
        fetcher._success_count = 10
        fetcher._error_count = 2
        fetcher._rate_limit_count = 1

        stats = fetcher.get_stats()

        assert stats["success_count"] == 10
        assert stats["error_count"] == 2
        assert stats["rate_limit_count"] == 1
        assert stats["total_requests"] == 13
