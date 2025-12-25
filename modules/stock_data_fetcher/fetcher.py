"""Stock data fetcher using Yahoo Finance."""

import time
from datetime import date, datetime
from typing import Any

import polars as pl
import yfinance as yf

from modules.common.exceptions import DataFetchError, RateLimitError
from modules.common.logger import get_logger
from modules.common.validators import validate_dataframe, validate_symbol

logger = get_logger(__name__)


class YahooFinanceFetcher:
    """Fetches stock data from Yahoo Finance with rate limiting and error handling."""

    def __init__(
        self,
        rate_limit_delay: float = 2.0,
        max_retries: int = 5,
        retry_delay: int = 60,
        timeout: int = 900,
    ) -> None:
        """Initialize Yahoo Finance fetcher.

        Args:
            rate_limit_delay: Seconds to wait between symbol requests
            max_retries: Maximum number of retry attempts
            retry_delay: Initial retry delay in seconds (exponential backoff)
            timeout: Request timeout in seconds
        """
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.symbols_fetched = 0
        self.symbols_failed = 0

    def fetch_single_symbol(
        self, symbol: str, fetch_date: date | None = None
    ) -> dict[str, Any] | None:
        """Fetch data for a single symbol with retry logic.

        Args:
            symbol: Stock symbol to fetch
            fetch_date: Specific date to fetch (None for latest)

        Returns:
            Dictionary with OHLCV data, or None if fetch fails

        Raises:
            RateLimitError: If rate limit exceeded after all retries
        """
        validate_symbol(symbol)

        # Determine period
        if fetch_date:
            period = "1d"
            start_date = fetch_date
            end_date = fetch_date
        else:
            period = "1d"
            start_date = None
            end_date = None

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Fetching {symbol} (attempt {attempt + 1}/{self.max_retries})",
                    symbol=symbol,
                    attempt=attempt + 1,
                )

                # Fetch data
                ticker = yf.Ticker(symbol)

                if start_date and end_date:
                    data = ticker.history(
                        start=start_date,
                        end=end_date,
                        timeout=self.timeout,
                        progress=False,
                    )
                else:
                    data = ticker.history(
                        period=period, timeout=self.timeout, progress=False
                    )

                if data.empty:
                    logger.warning(f"No data returned for {symbol}", symbol=symbol)
                    self.symbols_failed += 1
                    return None

                # Convert to dictionary
                result = {
                    "symbol": symbol,
                    "date": (
                        data.index[0].date()
                        if not data.empty
                        else fetch_date or date.today()
                    ),
                    "open": float(data["Open"].iloc[0]) if not data.empty else 0.0,
                    "high": float(data["High"].iloc[0]) if not data.empty else 0.0,
                    "low": float(data["Low"].iloc[0]) if not data.empty else 0.0,
                    "close": float(data["Close"].iloc[0]) if not data.empty else 0.0,
                    "volume": int(data["Volume"].iloc[0]) if not data.empty else 0,
                    "adjusted_close": (
                        float(data["Close"].iloc[0]) if not data.empty else 0.0
                    ),
                }

                logger.info(f"Successfully fetched {symbol}", symbol=symbol)
                self.symbols_fetched += 1
                return result

            except Exception as e:
                error_str = str(e).lower()

                # Check if it's a rate limit error
                if "429" in error_str or "too many requests" in error_str:
                    logger.warning(
                        f"Rate limited on {symbol}, attempt {attempt + 1}",
                        symbol=symbol,
                        attempt=attempt + 1,
                    )

                    if attempt < self.max_retries - 1:
                        # Exponential backoff
                        delay = self.retry_delay * (2**attempt)
                        logger.info(
                            f"Waiting {delay}s before retry",
                            symbol=symbol,
                            delay=delay,
                        )
                        time.sleep(delay)
                        continue
                    else:
                        self.symbols_failed += 1
                        raise RateLimitError(
                            f"Rate limit exceeded for {symbol} after {self.max_retries} attempts",
                            details={"symbol": symbol, "attempts": self.max_retries},
                        )

                # Other errors
                logger.error(
                    f"Error fetching {symbol}: {e}",
                    symbol=symbol,
                    error=str(e),
                    attempt=attempt + 1,
                )

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.info(
                        f"Retrying {symbol} in {delay}s", symbol=symbol, delay=delay
                    )
                    time.sleep(delay)
                else:
                    self.symbols_failed += 1
                    logger.error(
                        f"Failed to fetch {symbol} after {self.max_retries} attempts",
                        symbol=symbol,
                    )
                    return None

        return None

    def fetch_multiple_symbols(
        self, symbols: list[str], fetch_date: date | None = None
    ) -> pl.DataFrame:
        """Fetch data for multiple symbols with rate limiting.

        Args:
            symbols: List of stock symbols to fetch
            fetch_date: Specific date to fetch (None for latest)

        Returns:
            Polars DataFrame with OHLCV data for all symbols

        Raises:
            DataFetchError: If no symbols could be fetched
        """
        results = []

        for i, symbol in enumerate(symbols):
            result = self.fetch_single_symbol(symbol, fetch_date)

            if result:
                results.append(result)

            # Rate limiting delay (except for last symbol)
            if i < len(symbols) - 1:
                logger.debug(
                    f"Rate limit delay: {self.rate_limit_delay}s",
                    delay=self.rate_limit_delay,
                )
                time.sleep(self.rate_limit_delay)

        if not results:
            raise DataFetchError(
                "Failed to fetch data for any symbols",
                details={
                    "symbols_attempted": len(symbols),
                    "symbols_fetched": 0,
                },
            )

        # Convert to Polars DataFrame
        df = pl.DataFrame(results)

        # Validate data
        errors = validate_dataframe(df)
        if errors:
            logger.warning(
                f"Data validation found {len(errors)} errors",
                error_count=len(errors),
                errors=errors[:5],  # Log first 5 errors
            )

        logger.info(
            f"Fetch complete: {self.symbols_fetched} succeeded, {self.symbols_failed} failed",
            symbols_fetched=self.symbols_fetched,
            symbols_failed=self.symbols_failed,
            total_symbols=len(symbols),
        )

        return df

    def get_stats(self) -> dict[str, int]:
        """Get fetch statistics.

        Returns:
            Dictionary with fetch statistics
        """
        return {
            "symbols_fetched": self.symbols_fetched,
            "symbols_failed": self.symbols_failed,
            "total_symbols": self.symbols_fetched + self.symbols_failed,
        }
