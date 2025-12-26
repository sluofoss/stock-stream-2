# API Specification

## Module Interfaces

### 1. Stock Data Fetcher Module

#### Lambda Handler Interface
```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda handler for fetching stock data.
    
    Args:
        event: EventBridge event containing configuration
        context: AWS Lambda context object
        
    Returns:
        dict: {
            'statusCode': int,
            'body': str,
            'metadata': {
                'symbols_processed': int,
                'symbols_failed': List[str],
                'execution_time': float,
                's3_key': str
            }
        }
    """
```

#### Configuration Schema (config/symbols.json)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["symbols", "market"],
  "properties": {
    "symbols": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^[A-Z0-9]{1,5}$"
      },
      "minItems": 1
    },
    "market": {
      "type": "string",
      "enum": ["ASX", "NYSE", "NASDAQ"]
    },
    "update_frequency": {
      "type": "string",
      "enum": ["daily", "weekly"],
      "default": "daily"
    }
  }
}
```

#### Output Parquet Schema
```python
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class StockDailyData:
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: float
    
    # Metadata fields
    fetch_timestamp: str  # ISO 8601
    data_source: str = "yahoo_finance"
```

### 2. ASX Symbol Updater Module

#### Lambda Handler Interface
```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda handler for updating ASX symbols.
    
    Returns:
        dict: {
            'statusCode': int,
            'body': str,
            'changes': {
                'added': List[str],
                'removed': List[str],
                'modified': List[str]
            }
        }
    """
```

#### Symbol List Schema (S3: config/symbols.json)
```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class StockSymbol:
    symbol: str
    name: str
    sector: str
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    
@dataclass
class SymbolList:
    updated_at: datetime
    source: str  # "asx_official"
    version: str  # Semantic versioning
    symbols: List[StockSymbol]
```

### 3. Data Aggregator Module

#### Public API
```python
from typing import List, Optional
from datetime import date
import polars as pl

class DataAggregator:
    """Aggregates historical stock data from S3."""
    
    def __init__(self, bucket: str, region: str = "ap-southeast-2"):
        """Initialize data aggregator with S3 bucket configuration."""
        
    def load_all_data(self, lazy: bool = True) -> pl.DataFrame | pl.LazyFrame:
        """
        Load all historical data.
        
        Args:
            lazy: If True, return LazyFrame for memory efficiency
            
        Returns:
            DataFrame or LazyFrame with all historical data
        """
        
    def load_date_range(
        self,
        start_date: date,
        end_date: date,
        symbols: Optional[List[str]] = None
    ) -> pl.DataFrame:
        """
        Load data for specific date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            symbols: Optional list of symbols to filter
            
        Returns:
            DataFrame with filtered data
        """
        
    def load_symbols(self, symbols: List[str]) -> pl.DataFrame:
        """
        Load data for specific symbols (all dates).
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            DataFrame with symbol data
        """
        
    def get_latest_date(self) -> date:
        """Get the most recent date in the dataset."""
        
    def get_available_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        
    def get_date_range(self) -> tuple[date, date]:
        """Get the full date range available (min, max)."""
```

### 4. Technical Indicators Module

#### Base Indicator Interface
```python
from abc import ABC, abstractmethod
import polars as pl

class Indicator(ABC):
    """Base class for all technical indicators."""
    
    def __init__(self, **params):
        """Initialize indicator with parameters."""
        self.params = params
        
    @abstractmethod
    def calculate(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Calculate indicator values.
        
        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            
        Returns:
            DataFrame with additional indicator columns
        """
        
    @property
    @abstractmethod
    def required_columns(self) -> List[str]:
        """Return list of required input columns."""
        
    @property
    @abstractmethod
    def output_columns(self) -> List[str]:
        """Return list of output column names."""
```

#### Indicator Calculator
```python
class IndicatorCalculator:
    """Calculate multiple indicators for stock data."""
    
    def __init__(self, indicators: List[Indicator]):
        """Initialize with list of indicators to calculate."""
        
    def calculate_all(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Calculate all indicators for the given data.
        
        Args:
            df: DataFrame with stock data (single or multiple symbols)
            
        Returns:
            DataFrame with all indicator columns added
        """
        
    def calculate_for_symbol(self, df: pl.DataFrame, symbol: str) -> pl.DataFrame:
        """Calculate indicators for a single symbol."""
```

### 5. Backtesting Module

#### Strategy Interface
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

class Action(Enum):
    """Trading actions."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    
@dataclass
class Order:
    """Represents a trading order."""
    symbol: str
    action: Action
    quantity: int
    price: float
    date: date
    order_type: str = "market"  # market, limit, stop
    
@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    quantity: int
    entry_price: float
    entry_date: date
    current_price: float
    unrealized_pnl: float
    
class Portfolio:
    """Manages portfolio state during backtesting."""
    
    def __init__(self, initial_capital: float, commission: float = 0.001):
        """
        Initialize portfolio.
        
        Args:
            initial_capital: Starting cash amount
            commission: Commission rate (default 0.1%)
        """
        self.cash: float
        self.positions: dict[str, Position]
        self.closed_trades: List[Trade]
        self.transaction_history: List[Transaction]
        
    def execute_order(self, order: Order) -> bool:
        """Execute a trading order, returns True if successful."""
        
    def get_total_value(self, current_prices: dict[str, float]) -> float:
        """Calculate total portfolio value (cash + positions)."""
        
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol."""
        
class Strategy(ABC):
    """Base class for trading strategies."""
    
    def __init__(self, name: str, **params):
        """Initialize strategy with parameters."""
        
    @abstractmethod
    def on_data(
        self,
        date: date,
        symbol: str,
        data: dict,
        portfolio: Portfolio
    ) -> Optional[Order]:
        """
        Called on each data point.
        
        Args:
            date: Current date
            symbol: Stock symbol
            data: Dict with OHLCV and indicator values
            portfolio: Current portfolio state
            
        Returns:
            Order to execute, or None
        """
        
    def on_order_filled(self, order: Order, portfolio: Portfolio) -> None:
        """Called when an order is filled (optional override)."""
        
    def on_start(self) -> None:
        """Called before backtesting starts (optional override)."""
        
    def on_end(self, portfolio: Portfolio) -> None:
        """Called after backtesting ends (optional override)."""
```

#### Backtesting Engine
```python
from typing import List, Dict
import polars as pl

class BacktestEngine:
    """Run backtests for trading strategies."""
    
    def __init__(
        self,
        initial_capital: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.0005
    ):
        """
        Initialize backtesting engine.
        
        Args:
            initial_capital: Starting capital
            commission: Commission rate per trade
            slippage: Slippage rate per trade
        """
        
    def run(
        self,
        strategy: Strategy,
        data: pl.DataFrame,
        symbols: Optional[List[str]] = None
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy: Strategy to test
            data: Historical data with indicators
            symbols: Optional list of symbols to trade
            
        Returns:
            BacktestResult with performance metrics
        """
        
@dataclass
class BacktestResult:
    """Results from a backtest run."""
    strategy_name: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    trades: List[Trade]
    equity_curve: pl.DataFrame
    
    def to_dict(self) -> dict:
        """Convert results to dictionary."""
        
    def plot(self) -> None:
        """Plot equity curve and drawdown."""
```

## Environment Variables

### Required
```bash
# AWS Configuration
AWS_REGION=ap-southeast-2
S3_BUCKET_NAME=stock-stream-data

# Application Configuration
ENVIRONMENT=dev  # dev, staging, prod
LOG_LEVEL=INFO   # DEBUG, INFO, WARNING, ERROR

# Yahoo Finance (optional)
YAHOO_FINANCE_TIMEOUT=30
YAHOO_FINANCE_MAX_RETRIES=3

# ASX Scraping (optional)
ASX_BASE_URL=https://www.asx.com.au
ASX_SYMBOLS_ENDPOINT=/asx/research/ASXListedCompanies.csv
```

### Optional
```bash
# Notifications
SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-2:123456789012:stock-alerts

# Data Retention
S3_LIFECYCLE_DAYS=365
CLOUDWATCH_LOG_RETENTION_DAYS=30

# Development
LOCAL_DATA_PATH=./data
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
```

## Error Codes

### Lambda Function Responses

#### Success Codes
- `200`: Success
- `202`: Accepted (partial success)

#### Client Error Codes
- `400`: Invalid configuration
- `404`: Resource not found (symbol, date range)
- `422`: Data validation error

#### Server Error Codes
- `500`: Internal error
- `502`: External API error (Yahoo Finance, ASX)
- `503`: Service unavailable (rate limit)
- `504`: Timeout

### Error Response Format
```json
{
  "statusCode": 500,
  "error": {
    "code": "FETCH_ERROR",
    "message": "Failed to fetch data for symbol BHP",
    "details": {
      "symbol": "BHP",
      "date": "2025-12-25",
      "reason": "Connection timeout"
    }
  },
  "timestamp": "2025-12-25T10:30:00Z"
}
```

## Rate Limits

### Yahoo Finance
- **Rate Limit:** ~2000 requests/hour
- **Retry Strategy:** Exponential backoff (1s, 2s, 4s, 8s)
- **Batch Size:** Recommended 100 symbols per request

### ASX Website
- **Rate Limit:** Conservative (1 request per 5 seconds)
- **Retry Strategy:** Linear backoff (5s intervals)

## Data Validation Rules

### Stock Data Validation
1. `symbol`: Must match `^[A-Z0-9]{1,5}$`
2. `date`: Must be valid date, not in future
3. `open, high, low, close, adjusted_close`: Must be > 0
4. `high`: Must be >= `low`, `open`, `close`
5. `low`: Must be <= `high`, `open`, `close`
6. `volume`: Must be >= 0
7. No duplicate (symbol, date) pairs

### Indicator Validation
1. All indicator values must be finite (no inf, -inf)
2. NaN values allowed only for initial periods (warmup)
3. Indicator values must be within expected ranges

## Performance Requirements

### Lambda Functions
- **Cold Start:** < 5 seconds
- **Warm Execution:** < 30 seconds per 100 symbols
- **Memory Usage:** < 80% of allocated memory

### Data Aggregator
- **Load Time:** < 10 seconds for 1 year of data (100 symbols)
- **Memory:** < 2GB for 5 years of data (100 symbols)

### Backtesting
- **Execution Time:** < 1 minute per strategy per year per symbol
- **Memory:** < 4GB for complex strategies with multiple symbols
