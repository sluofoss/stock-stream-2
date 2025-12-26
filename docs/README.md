# Stock Stream 2

A serverless stock data pipeline and backtesting framework for ASX stocks, deployed on AWS.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Modules](#modules)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Usage](#usage)
- [Data Schema](#data-schema)
- [Technical Indicators](#technical-indicators)
- [Backtesting Framework](#backtesting-framework)
- [Development](#development)
- [Testing](#testing)
- [Cost Estimation](#cost-estimation)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

## Overview

This repository contains a serverless data pipeline for:
1. Fetching and storing daily stock data from Yahoo Finance
2. Maintaining up-to-date ASX stock symbol lists
3. Historical data aggregation and analysis
4. Technical indicator calculation
5. Strategy backtesting with stateful portfolio management

**Key Features:**
- One-command deployment via Terraform
- Serverless architecture (AWS Lambda)
- Efficient storage with Parquet format on S3
- High-performance data processing with Polars
- Extensible strategy backtesting framework

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ EventBridge  │────────>│   Lambda 1   │                  │
│  │  (Daily)     │         │ Stock Data   │                  │
│  └──────────────┘         │  Fetcher     │                  │
│                            └──────┬───────┘                  │
│                                   │                          │
│  ┌──────────────┐         ┌──────▼───────┐                  │
│  │ EventBridge  │────────>│   Lambda 2   │                  │
│  │  (Weekly)    │         │ ASX Symbol   │                  │
│  └──────────────┘         │   Updater    │                  │
│                            └──────┬───────┘                  │
│                                   │                          │
│                            ┌──────▼───────┐                  │
│                            │      S3      │                  │
│                            │   Bucket     │                  │
│                            │  (Parquet)   │                  │
│                            └──────┬───────┘                  │
│                                   │                          │
│                     ┌─────────────▼────────────┐             │
│                     │   Local/Lambda Module    │             │
│                     │  Data Aggregator +       │             │
│                     │  Indicator Calculator +  │             │
│                     │  Backtesting Engine      │             │
│                     └──────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

## Modules

### 1. Stock Data Fetcher (Lambda)
**Purpose:** Periodically download daily stock data from Yahoo Finance

**Specifications:**
- **Trigger:** EventBridge rule (daily, configurable time)
- **Runtime:** Python 3.12+
- **Dependencies:** `yfinance`, `polars`, `pyarrow`, `boto3`
- **Input:** Configuration file (`config/symbols.json`) containing stock symbols
- **Output:** Parquet files in S3 (`s3://bucket-name/raw-data/YYYY-MM-DD.parquet`)
- **Data per file:** Multiple stock symbols aggregated per day
- **Rate Limiting:** 2-second delay between symbols (built-in yfinance protection)
- **Error Handling:** Exponential backoff retry logic, failure notifications via SNS
- **Timeout:** 15 minutes (to handle rate limits gracefully)
- **Memory:** 512 MB

**Data Fields:**
- symbol (string)
- date (date)
- open (float)
- high (float)
- low (float)
- close (float)
- volume (int64)
- adjusted_close (float)

### 2. ASX Symbol Updater (Lambda)
**Purpose:** Maintain up-to-date list of ASX stock symbols

**Specifications:**
- **Trigger:** EventBridge rule (weekly, configurable)
- **Runtime:** Python 3.12+
- **Dependencies:** `requests`, `beautifulsoup4`, `boto3`
- **Source:** ASX official website
- **Output:** 
  - Updated `config/symbols.json` in S3
  - Versioned for rollback capability
- **Change Detection:** Compare with previous version, log additions/removals
- **Timeout:** 3 minutes
- **Memory:** 256 MB

**Symbol List Schema:**
```json
{
  "updated_at": "2025-12-25T00:00:00Z",
  "source": "asx_official",
  "symbols": [
    {
      "symbol": "BHP",
      "name": "BHP Group Limited",
      "sector": "Materials"
    }
  ]
}
```

### 3. Data Aggregator Module
**Purpose:** Read and consolidate all historical S3 data into a single in-memory dataset

**Specifications:**
- **Runtime:** Python module (can run locally or in Lambda)
- **Dependencies:** `polars`, `boto3`, `pyarrow`
- **Input:** S3 bucket path containing all parquet files
- **Output:** Single Polars DataFrame with all historical data
- **Memory Considerations:** Lazy loading with Polars scan_parquet for large datasets
- **Caching:** Optional local cache for development

**Key Functions:**
- `load_all_data(bucket: str, prefix: str) -> pl.DataFrame`
- `load_date_range(start_date: date, end_date: date) -> pl.DataFrame`
- `load_symbols(symbols: List[str]) -> pl.DataFrame`

### 4. Technical Indicators & Backtesting Module
**Purpose:** Calculate technical indicators and perform strategy backtesting

**Specifications:**
- **Runtime:** Python module
- **Dependencies:** `polars`, `numpy`
- **Input:** Polars DataFrame from Data Aggregator
- **Processing:** Per-symbol iterative/recursive calculation
- **Performance:** Optimized for daily data (not intraday)

**Components:**

#### Technical Indicators Calculator
- Moving Averages (SMA, EMA, WMA)
- Momentum Indicators (RSI, MACD, Stochastic)
- Volatility Indicators (Bollinger Bands, ATR)
- Volume Indicators (OBV, VWAP)
- Extensible indicator framework

#### Backtesting Engine
- **Strategy Interface:** Abstract base class for custom strategies
- **State Management:** Stateful portfolio tracking per strategy
- **Position Management:** Long/short positions, position sizing
- **Performance Metrics:** Returns, Sharpe ratio, max drawdown, win rate
- **Transaction Costs:** Configurable commission and slippage

**Strategy Interface:**
```python
class Strategy(ABC):
    @abstractmethod
    def on_data(self, date: date, symbol: str, data: dict, portfolio: Portfolio) -> Action
    
    @abstractmethod
    def on_order_filled(self, order: Order, portfolio: Portfolio) -> None
```

## Prerequisites

- **AWS Account** with appropriate permissions (Lambda, S3, EventBridge, IAM, CloudWatch)
- **Terraform** >= 1.5.0
- **Python** >= 3.12
- **uv** package manager
- **AWS CLI** configured with credentials

## Setup & Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd stock-stream-2
```

### 2. Install Dependencies
```bash
# Using uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### 3. Configure AWS Credentials
```bash
aws configure
```

### 4. Initialize Terraform
```bash
cd terraform
terraform init
```

## Configuration

### 1. Environment Variables
Create `.env` file:
```env
AWS_REGION=ap-southeast-2
S3_BUCKET_NAME=stock-stream-data
ENVIRONMENT=dev
LOG_LEVEL=INFO
```

### 2. Stock Symbols Configuration
Edit `config/symbols.json`:
```json
{
  "symbols": ["BHP", "CBA", "NAB", "WBC", "ANZ"],
  "update_frequency": "daily",
  "market": "ASX"
}
```

### 3. Lambda Configuration
Edit `terraform/variables.tf` for:
- Lambda memory allocation
- Timeout settings
- Schedule expressions
- SNS notification emails

## Deployment

### One-Command Deployment
```bash
cd terraform
terraform apply -auto-approve
```

### Manual Deployment Steps
```bash
# 1. Package Lambda functions
make package-lambdas

# 2. Plan infrastructure changes
terraform plan -out=tfplan

# 3. Apply changes
terraform apply tfplan
```

### Deployment Outputs
- Lambda function ARNs
- S3 bucket name
- CloudWatch log group names
- EventBridge rule ARNs

## Usage

### Running Data Fetcher Locally
```bash
python -m modules.stock_data_fetcher.main --config config/symbols.json --output data/
```

### Running Backtest
```bash
python -m modules.backtesting.main \
  --strategy MovingAverageCrossover \
  --start-date 2020-01-01 \
  --end-date 2023-12-31 \
  --symbols BHP,CBA \
  --initial-capital 100000
```

### Viewing Logs
```bash
# Lambda logs
aws logs tail /aws/lambda/stock-data-fetcher --follow

# Specific date range
aws logs filter-pattern /aws/lambda/stock-data-fetcher --start-time 2025-12-24T00:00:00 --end-time 2025-12-25T00:00:00
```

## Data Schema

### Raw Data Schema (Parquet)
```
symbol: String
date: Date32
open: Float64
high: Float64
low: Float64
close: Float64
volume: Int64
adjusted_close: Float64
```

### Processed Data Schema (with Indicators)
Additional columns added by indicator calculator:
```
sma_20: Float64
sma_50: Float64
ema_12: Float64
ema_26: Float64
rsi_14: Float64
macd: Float64
macd_signal: Float64
bollinger_upper: Float64
bollinger_lower: Float64
atr_14: Float64
```

## Technical Indicators

### Supported Indicators
1. **Simple Moving Average (SMA)** - Configurable periods
2. **Exponential Moving Average (EMA)** - Configurable periods
3. **Relative Strength Index (RSI)** - Default 14 periods
4. **MACD** - (12, 26, 9) default configuration
5. **Bollinger Bands** - 20 period, 2 standard deviations
6. **Average True Range (ATR)** - 14 periods
7. **On-Balance Volume (OBV)**
8. **Stochastic Oscillator** - (14, 3, 3) default

### Adding Custom Indicators
```python
from modules.indicators.base import Indicator

class CustomIndicator(Indicator):
    def calculate(self, df: pl.DataFrame) -> pl.DataFrame:
        # Implementation
        pass
```

## Backtesting Framework

### Portfolio State
- Cash balance
- Open positions (symbol, quantity, entry price, entry date)
- Closed positions history
- Transaction history

### Strategy Examples

#### Moving Average Crossover
```python
class MovingAverageCrossover(Strategy):
    def __init__(self, fast_period=20, slow_period=50):
        self.fast_period = fast_period
        self.slow_period = slow_period
```

#### RSI Mean Reversion
```python
class RSIMeanReversion(Strategy):
    def __init__(self, oversold=30, overbought=70):
        self.oversold = oversold
        self.overbought = overbought
```

### Performance Metrics
- Total Return (%)
- Annualized Return (%)
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown (%)
- Win Rate (%)
- Profit Factor
- Average Win / Average Loss

## Development

### Project Structure
```
stock-stream-2/
├── modules/
│   ├── stock_data_fetcher/     # Lambda 1
│   │   ├── main.py
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── asx_symbol_updater/     # Lambda 2
│   │   ├── main.py
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── data_aggregator/        # Module 3
│   │   ├── loader.py
│   │   └── cache.py
│   ├── indicators/             # Module 4 - Indicators
│   │   ├── base.py
│   │   ├── trend.py
│   │   ├── momentum.py
│   │   └── volatility.py
│   └── backtesting/            # Module 4 - Backtesting
│       ├── strategy.py
│       ├── portfolio.py
│       ├── engine.py
│       └── metrics.py
├── config/
│   ├── symbols.json
│   └── strategies.yaml
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── lambda.tf
│   ├── s3.tf
│   ├── eventbridge.tf
│   └── outputs.tf
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/
│   ├── local_backtest.py
│   └── data_quality_check.py
├── .env.example
├── .gitignore
├── Makefile
├── pyproject.toml
└── README.md
```

### Makefile Targets
```bash
make install        # Install dependencies
make test          # Run all tests
make test-unit     # Run unit tests only
make lint          # Run linters (ruff, mypy)
make format        # Format code (black, isort)
make package       # Package Lambda functions
make deploy        # Deploy to AWS
make clean         # Clean build artifacts
```

### Code Quality
- **Linting:** ruff
- **Type Checking:** mypy
- **Formatting:** black, isort
- **Testing:** pytest
- **Coverage:** pytest-cov (target: 80%+)

## Testing

### Unit Tests
```bash
pytest tests/unit -v
```

### Integration Tests
```bash
# Requires AWS credentials
pytest tests/integration -v --aws
```

### End-to-End Tests
```bash
# Test full pipeline
python scripts/e2e_test.py
```

### Test Coverage
```bash
pytest --cov=modules --cov-report=html
open htmlcov/index.html
```

## Cost Estimation

### Monthly AWS Costs (Approximate)
- **S3 Storage:** $0.023/GB (est. $5-10 for 1 year of daily data)
- **Lambda Invocations:** 
  - Data Fetcher: 30 invocations/month × 300s = $0.10
  - Symbol Updater: 4 invocations/month × 60s = $0.01
- **Data Transfer:** Negligible (within same region)
- **CloudWatch Logs:** $0.50/GB (est. $1-2/month)

**Total Estimated Cost:** $7-15/month

### Cost Optimization Tips
- Use S3 Intelligent-Tiering for older data
- Compress Parquet files with Snappy/Zstd
- Set CloudWatch log retention policies
- Use Lambda reserved concurrency for cost control

## Troubleshooting

### Common Issues

#### Lambda Timeout
**Symptom:** Function times out before completing
**Solution:** 
- Increase timeout in `terraform/lambda.tf`
- Reduce number of symbols per invocation
- Optimize data fetching logic

#### S3 Permission Denied
**Symptom:** `AccessDenied` error when writing to S3
**Solution:**
- Check IAM role attached to Lambda
- Verify S3 bucket policy
- Ensure correct AWS region

#### Polars Memory Error
**Symptom:** `MemoryError` when loading large datasets
**Solution:**
- Use `pl.scan_parquet()` for lazy loading
- Filter date ranges before collecting
- Increase available memory (local) or Lambda memory

#### Yahoo Finance Rate Limiting
**Symptom:** 429 Too Many Requests errors
**Solution:**
- Add delays between requests
- Implement exponential backoff
- Consider using batch API if available

## Roadmap

### Phase 1 (Current) - MVP
- [x] Project structure setup
- [ ] Lambda 1: Stock data fetcher
- [ ] Lambda 2: ASX symbol updater
- [ ] Module 3: Data aggregator
- [ ] Module 4: Basic indicators & backtesting
- [ ] Terraform deployment

### Phase 2 - Enhancement
- [ ] Real-time data ingestion (WebSocket)
- [ ] Additional technical indicators (50+)
- [ ] Multi-strategy portfolio optimization
- [ ] Web dashboard for visualization
- [ ] Notification system (email/SMS on signals)

### Phase 3 - Advanced
- [ ] Machine learning integration
- [ ] Sentiment analysis from news
- [ ] Options trading strategies
- [ ] Paper trading environment
- [ ] Live trading integration (with safeguards)

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

[Your License Here]

## Contact

[Your Contact Information]

---

**Last Updated:** December 25, 2025
