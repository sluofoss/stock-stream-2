# API Specification

## Overview

The Stock Stream 2 system uses AWS Step Functions to orchestrate a daily pipeline that:
1. Updates ASX symbol list via Lambda
2. Splits symbols into batches of 100
3. Invokes parallel Lambda instances to fetch stock data
4. Stores results as Parquet files in S3

## Module Interfaces

### 1. Stock Data Fetcher Module

#### Lambda Handler Interface
```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda handler for fetching stock data for a batch of symbols.
    Invoked by Step Functions with a batch of up to 100 symbols.
    
    Args:
        event: Step Functions event containing:
            {
                "symbols": List[str],  # Up to 100 symbols
                "date": str,           # Optional: ISO date format
                "batchNumber": int     # Batch identifier
            }
        context: AWS Lambda context object
        
    Returns:
        dict: {
            'statusCode': int,
            'body': str,
            'metadata': {
                'batch_number': int,
                'symbols_processed': int,
                'symbols_fetched': int,
                'symbols_failed': List[str],
                'execution_time': float,
                's3_key': str  # e.g., "raw-data/2025-12-26-batch-0.parquet"
            }
        }
    """
```

#### Input Event Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["symbols", "batchNumber"],
  "properties": {
    "symbols": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^[A-Z0-9]{1,5}$"
      },
      "minItems": 1,
      "maxItems": 100
    },
    "batchNumber": {
      "type": "integer",
      "minimum": 0
    },
    "date": {
      "type": "string",
      "format": "date",
      "description": "Optional: ISO 8601 date (YYYY-MM-DD)"
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
    batch_number: int     # Which batch this came from
    data_source: str = "yahoo_finance"
```

#### S3 Output Structure
```
s3://bucket-name/
├── raw-data/
│   ├── 2025-12-26-batch-0.parquet   # First 100 symbols
│   ├── 2025-12-26-batch-1.parquet   # Next 100 symbols
│   ├── 2025-12-26-batch-2.parquet   # Next 100 symbols
│   └── ...
└── symbols/
    └── 2025-12-26-symbols.csv
```

### 2. ASX Symbol Updater Module

#### Lambda Handler Interface
```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda handler for updating ASX symbols.
    First step in Step Functions workflow.
    
    Workflow:
    1. Downloads CSV from ASX website (https://www.asx.com.au/markets/trade-our-cash-market/directory)
    2. Uploads CSV to S3: symbols/YYYY-MM-DD-symbols.csv
    3. Retrieves latest file from S3 (the one just uploaded)
    4. Splits symbols into batches of 100
    5. Returns formatted output for Step Functions
    
    Args:
        event: Step Functions initiation event (typically empty or with date override)
        context: AWS Lambda context object
    
    Returns:
        dict: {
            'statusCode': int,
            'body': str,
            'symbols': List[str],           # All symbols (flat list)
            'symbolBatches': List[dict],    # Batched for Step Functions Map
            'metadata': {
                'total_symbols': int,
                'num_batches': int,
                'batch_size': int,
                's3_key': str,              # CSV location
                'execution_time': float
            }
        }
    
    Environment Variables Required:
        S3_BUCKET: S3 bucket name for storing symbols CSV
    """
```

#### Implementation Details

**CSV Download Process:**
1. Fetches HTML from ASX directory page
2. Parses HTML to find CSV download link using BeautifulSoup
3. Extracts download URL from link's onclick or href attribute
4. Downloads CSV file
5. Validates CSV contains company data

**CSV Parsing:**
- Handles various column name formats:
  - Symbol: 'ASX code', 'Code', 'Symbol', 'Ticker'
  - Name: 'Company name', 'Name', 'Company'
  - Sector: 'GICS industry group', 'Industry', 'Sector'
  - Market Cap: 'Market Cap', 'MarketCap'
- Filters out invalid rows (missing symbol or name)
- Returns list of company dictionaries

**Batch Splitting:**
- Batch size: 100 symbols (configurable via BATCH_SIZE constant)
- Each batch includes: symbols array and batchNumber
- Example: 2147 symbols → 22 batches (21 full + 1 partial)

#### Output Format for Step Functions
```json
{
  "statusCode": 200,
  "body": "{...}",
  "symbols": ["BHP", "CBA", "NAB", ...],
  "symbolBatches": [
    {
      "symbols": ["BHP", "CBA", ...],
      "batchNumber": 0
    },
    {
      "symbols": ["WBC", "ANZ", ...],
      "batchNumber": 1
    }
  ],
  "metadata": {
    "request_id": "abc-123",
    "timestamp": "2025-12-26T00:00:00Z",
    "total_symbols": 2147,
    "num_batches": 22,
    "batch_size": 100,
    "s3_key": "symbols/2025-12-26-symbols.csv",
    "execution_time": 45.3
  }
}
```

#### CSV Output Schema (S3)
The downloaded CSV is stored as-is from ASX website. Typical columns:
```csv
symbol,name,sector,market_cap
BHP,BHP Group Limited,Materials,180500000000
CBA,Commonwealth Bank,Financials,165200000000
NAB,National Australia Bank,Financials,98450000000
```

Note: Column names may vary based on ASX website format. The parser handles multiple formats.

### 3. Step Functions State Machine

#### State Machine Definition
```json
{
  "Comment": "Daily Stock Data Pipeline - Fetch ASX symbols and stock data in parallel batches",
  "StartAt": "UpdateASXSymbols",
  "States": {
    "UpdateASXSymbols": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:asx-symbol-updater",
      "Comment": "Step 1: Fetch latest ASX symbols and export to CSV",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyFailure",
          "ResultPath": "$.error"
        }
      ],
      "Next": "SplitIntoBatches"
    },
    "SplitIntoBatches": {
      "Type": "Map",
      "Comment": "Step 2: Process symbol batches in parallel (max 10 concurrent)",
      "ItemsPath": "$.symbolBatches",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "FetchStockData",
        "States": {
          "FetchStockData": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:stock-data-fetcher",
            "Comment": "Fetch stock data for batch of 100 symbols",
            "Retry": [
              {
                "ErrorEquals": ["States.TaskFailed"],
                "IntervalSeconds": 30,
                "MaxAttempts": 2,
                "BackoffRate": 1.5
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.batchError",
                "Next": "BatchFailed"
              }
            ],
            "End": true
          },
          "BatchFailed": {
            "Type": "Pass",
            "Comment": "Mark batch as failed but continue processing other batches",
            "Result": {
              "status": "failed"
            },
            "End": true
          }
        }
      },
      "ResultPath": "$.batchResults",
      "Next": "AggregateResults"
    },
    "AggregateResults": {
      "Type": "Pass",
      "Comment": "Collect results from all batches",
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:stock-stream-alerts",
        "Subject": "Stock Stream Pipeline Failed",
        "Message.$": "$.error"
      },
      "End": true
    }
  }
}
```

#### Execution Flow
```
1. EventBridge (Daily Trigger)
        ↓
2. Step Functions: UpdateASXSymbols
        ↓
3. Lambda: ASX Symbol Updater
        ↓ (returns symbolBatches array)
4. Step Functions: Map State (parallel)
        ↓
5. Lambda: Stock Data Fetcher (×N instances)
        ↓
6. S3: Multiple Parquet files (batch-0, batch-1, ...)
        ↓
7. Step Functions: AggregateResults
        ↓
8. End (or NotifyFailure on error)
```

#### Timing Estimates
- **ASX Symbol Update:** 1-2 minutes
- **Single Batch (100 symbols):** 3-4 minutes
- **10 Parallel Batches (1000 symbols):** 3-4 minutes (same as single, runs in parallel)
- **Total Pipeline (1000 symbols):** ~5-6 minutes

#### Cost Estimates (Per Daily Run)
- **Step Functions:** ~$0.000025 per state transition (~10 transitions = $0.00025)
- **Lambda (ASX Updater):** ~$0.001
- **Lambda (Stock Fetcher):** ~$0.01 per batch × 10 batches = $0.10
- **S3 Storage:** ~$0.023 per GB/month
- **Total Daily Cost:** ~$0.10
- **Monthly Cost:** ~$3.00

### 4. Data Aggregator Module

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
