# Command Reference - Stock Stream 2

Quick reference for common development tasks.

## Environment Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Update dependencies
uv pip install --upgrade -e ".[dev]"
```

## Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests with coverage
make test-cov

# Run specific test file
pytest tests/unit/test_validators.py -v

# Run specific test class
pytest tests/unit/test_validators.py::TestValidateSymbol -v

# Run specific test
pytest tests/unit/test_validators.py::TestValidateSymbol::test_valid_symbols -v

# Run tests matching pattern
pytest -k "validator" -v
```

## Code Quality

```bash
# Run all quality checks
make lint

# Run ruff linter
make ruff

# Format code with black
make format

# Type check with mypy
make mypy

# Run pre-commit hooks
pre-commit run --all-files
```

## Building

```bash
# Build Lambda package for stock data fetcher
python scripts/build_lambda.py \
  --module stock_data_fetcher \
  --output dist/stock_data_fetcher.zip \
  --optimize

# Build without optimization
python scripts/build_lambda.py \
  --module stock_data_fetcher \
  --output dist/stock_data_fetcher.zip
```

## AWS Deployment

```bash
# Deploy Lambda function
aws lambda update-function-code \
  --function-name stock-stream-stock-data-fetcher \
  --zip-file fileb://dist/stock_data_fetcher.zip

# Test Lambda locally (requires SAM CLI)
sam local invoke StockDataFetcher \
  --event events/test-event.json

# View Lambda logs
aws logs tail /aws/lambda/stock-stream-stock-data-fetcher --follow

# Invoke Lambda manually
aws lambda invoke \
  --function-name stock-stream-stock-data-fetcher \
  --payload '{"start_date":"2024-01-01","end_date":"2024-01-31"}' \
  response.json
```

## S3 Operations

```bash
# List S3 buckets
aws s3 ls

# Upload config file
aws s3 cp config/symbols.json s3://stock-data-bucket/config/symbols.json

# List raw data
aws s3 ls s3://stock-data-bucket/raw/ --recursive

# Download data
aws s3 cp s3://stock-data-bucket/raw/BHP/2024-01-01.parquet ./data/

# Sync entire raw folder
aws s3 sync s3://stock-data-bucket/raw/ ./data/raw/
```

## Development

```bash
# Start Jupyter notebook
jupyter notebook

# Start Jupyter lab
jupyter lab

# Run Python REPL
ipython

# Check Python version
python --version

# Check installed packages
pip list

# Show package info
pip show polars
```

## Git Operations

```bash
# Check status
git status

# Stage all changes
git add .

# Commit with message
git commit -m "Implement stock data fetcher module"

# Push to remote
git push origin main

# Create new branch
git checkout -b feature/new-feature

# View commit history
git log --oneline --graph

# View file changes
git diff modules/stock_data_fetcher/fetcher.py
```

## Debugging

```bash
# Run tests with debugger on failure
pytest --pdb

# Run tests with print statements visible
pytest -s

# Increase test verbosity
pytest -vv

# Show local variables on failure
pytest --showlocals

# Run specific test with debugging
pytest tests/unit/test_fetcher.py::TestYahooFinanceFetcher::test_fetch_single_symbol_success --pdb
```

## Environment Variables

```bash
# Set environment variable for current session
export S3_BUCKET=my-test-bucket

# Load from .env file
set -a; source .env; set +a

# Show all environment variables
env | grep STOCK

# Unset environment variable
unset S3_BUCKET
```

## Data Operations

```bash
# Read Parquet file with Python
python -c "import polars as pl; df = pl.read_parquet('data.parquet'); print(df)"

# Convert CSV to Parquet
python -c "import polars as pl; pl.read_csv('data.csv').write_parquet('data.parquet')"

# Check Parquet file size
ls -lh data.parquet

# Count rows in Parquet
python -c "import polars as pl; print(len(pl.read_parquet('data.parquet')))"
```

## Cleanup

```bash
# Remove build artifacts
make clean

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Remove test artifacts
rm -rf .pytest_cache htmlcov .coverage

# Remove virtual environment
rm -rf .venv
```

## Monitoring

```bash
# Watch Lambda invocations
watch -n 5 'aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=stock-stream-stock-data-fetcher \
  --start-time $(date -u -d "1 hour ago" +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum'

# View Lambda error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=stock-stream-stock-data-fetcher \
  --start-time $(date -u -d "1 day ago" +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

## Makefile Targets

All available make targets:

```bash
# Installation
make install          # Install production dependencies
make install-dev      # Install development dependencies

# Testing
make test            # Run all tests
make test-unit       # Run unit tests
make test-integration # Run integration tests
make test-cov        # Run tests with coverage report

# Code Quality
make lint            # Run all linters
make format          # Format code
make ruff            # Run ruff
make mypy            # Run type checker

# Building
make build           # Build all Lambda packages
make build-fetcher   # Build stock data fetcher package

# Deployment
make deploy          # Deploy all infrastructure
make deploy-lambda   # Deploy Lambda functions

# Cleanup
make clean           # Remove build artifacts
make clean-pyc       # Remove Python cache files

# Documentation
make docs            # Generate documentation
make docs-serve      # Serve documentation locally
```

## Quick Workflows

### Starting a new feature
```bash
git checkout -b feature/my-feature
source .venv/bin/activate
# Make changes...
make lint
make test
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

### Running full CI pipeline locally
```bash
make clean
make install-dev
make format
make lint
make test-cov
make build
```

### Deploying to AWS
```bash
make clean
make build
make deploy
aws logs tail /aws/lambda/stock-stream-stock-data-fetcher --follow
```

### Debugging failed tests
```bash
pytest --lf --pdb  # Run last failed tests with debugger
pytest -x --pdb    # Stop on first failure and debug
```
