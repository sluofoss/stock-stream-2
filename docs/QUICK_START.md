# Quick Start Guide

Get started with Stock Stream 2 in under 10 minutes.

## Prerequisites

Ensure you have the following installed:
- Python 3.12+
- uv package manager
- AWS CLI
- Terraform 1.5+
- Git

## Architecture Overview

The system uses **AWS Step Functions** to orchestrate a daily pipeline:

1. **Step 1:** Lambda updates ASX symbol list → exports CSV to S3
2. **Step 2:** Step Functions splits symbols into batches of 100
3. **Step 3:** Multiple Lambda instances fetch data in parallel (max 10 concurrent)
4. **Step 4:** Each Lambda saves batch as Parquet file to S3

**Benefits:**
- Process 1000+ symbols in ~5 minutes
- Parallel execution with fault isolation
- Automatic retry on failures
- Cost-efficient (~$3/month)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd stock-stream-2

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install polars pyarrow boto3 yfinance requests beautifulsoup4 python-dotenv loguru

# For development (includes pytest, mypy, ruff, etc.)
# uv pip install pytest pytest-cov pytest-mock mypy ruff black moto
```

## Step 1.5: Test Locally (Optional but Recommended)

Before deploying to AWS, test the modules locally:

### Test ASX Symbol Updater

```bash
# Run with mock data (no AWS required)
python scripts/run_asx_updater_local.py
```

You should see output like:
```
================================================================================
ASX Symbol Updater - Local Test Mode
================================================================================

Running with mock data (no AWS S3 access required)

...logs...

================================================================================
Execution Complete
================================================================================

Status Code: 200
✅ SUCCESS
  - Total Symbols: 10
  - Number of Batches: 1
  - Batch Size: 100
  - S3 Key: symbols/2025-12-26-symbols.csv
  - Execution Time: 0.001s

Symbol Batches:
  - Batch 0: 10 symbols
```

This confirms:
- Python environment is set up correctly
- All dependencies are installed
- The module logic works
- Step Functions output format is correct

## Step 2: Configure AWS

```bash
# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Region: ap-southeast-2
# Output format: json

# Verify configuration
aws sts get-caller-identity
```

## Step 3: Set Up Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor

# Required changes:
# - AWS_ACCOUNT_ID: Your AWS account ID
# - S3_BUCKET_NAME: Unique bucket name (globally unique)
# - SNS_ALERTS_EMAIL: Your email for notifications
```

## Step 4: Create Initial Configuration

```bash
# Create config directory
mkdir -p config

# Create initial symbols list
cat > config/symbols.json << EOF
{
  "symbols": ["BHP", "CBA", "NAB", "WBC", "ANZ", "CSL", "WES", "WOW", "FMG", "RIO"],
  "update_frequency": "daily",
  "market": "ASX"
}
EOF
```

## Step 5: Deploy Infrastructure

```bash
# Initialize Terraform
cd terraform
terraform init

# Review deployment plan
terraform plan

# Deploy (this will take 3-5 minutes)
terraform apply -auto-approve

# Note the outputs (S3 bucket name, Lambda ARNs, etc.)
cd ..
```

## Step 6: Test Locally (Optional)

Before relying on Lambda functions, test locally:

```bash
# Fetch stock data locally
python -m scripts.fetch_data_local --symbols BHP,CBA,NAB --days 30

# Verify data was fetched
ls -lh data/

# Upload to S3 (optional)
aws s3 sync data/ s3://your-bucket-name/raw-data/
```

## Step 7: Run Your First Backtest

```bash
# Run a simple moving average crossover strategy
python -m scripts.local_backtest \
  --strategy MovingAverageCrossover \
  --symbols BHP,CBA \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000

# View results
cat backtest_results.json
```

## Step 8: Monitor Lambda Execution

```bash
# Trigger data fetcher Lambda manually (for testing)
aws lambda invoke \
  --function-name stock-data-fetcher \
  --payload '{}' \
  response.json

# View the response
cat response.json

# Check Lambda logs
aws logs tail /aws/lambda/stock-data-fetcher --follow

# List files in S3
aws s3 ls s3://your-bucket-name/raw-data/ --recursive
```

## Step 9: Verify Data Pipeline

```bash
# Check if data is being collected
python -m scripts.data_quality_check \
  --bucket your-bucket-name \
  --start-date 2024-01-01

# Expected output:
# ✓ Found X files
# ✓ Date range: 2024-01-01 to 2024-12-25
# ✓ X unique symbols
# ✓ No missing dates
# ✓ Data validation passed
```

## Step 10: Set Up Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name stock-stream-2 \
  --dashboard-body file://config/cloudwatch_dashboard.json

# Set up billing alert
aws cloudwatch put-metric-alarm \
  --alarm-name stock-stream-high-cost \
  --alarm-description "Alert if daily cost exceeds $5" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold
```

## Common Commands

### Data Management
```bash
# Download all data from S3
python -m scripts.download_s3_data --output ./local_data

# Check data quality
python -m scripts.data_quality_check

# Clear local cache
python -m scripts.clear_cache
```

### Backtesting
```bash
# Run backtest with custom parameters
python -m modules.backtesting.main \
  --strategy RSIMeanReversion \
  --symbols BHP,CBA,NAB,WBC,ANZ \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000 \
  --commission 0.001 \
  --output results/

# Compare multiple strategies
python -m scripts.strategy_comparison \
  --strategies MovingAverageCrossover,RSIMeanReversion \
  --symbols BHP,CBA \
  --start-date 2023-01-01
```

### Maintenance
```bash
# Update symbol list manually
python -m modules.asx_symbol_updater.main

# Force data refresh for specific date
python -m modules.stock_data_fetcher.main \
  --date 2024-12-25 \
  --symbols BHP,CBA

# Clean up old data (older than 1 year)
python -m scripts.cleanup_old_data --days 365
```

### Development
```bash
# Run tests
make test

# Run linting
make lint

# Format code
make format

# Type check
mypy modules/

# Generate coverage report
pytest --cov=modules --cov-report=html
```

## Troubleshooting

### Lambda Function Not Triggering
```bash
# Check EventBridge rule
aws events list-rules --name-prefix stock-

# Check Lambda permissions
aws lambda get-policy --function-name stock-data-fetcher

# Enable EventBridge rule if disabled
aws events enable-rule --name stock-data-fetcher-daily
```

### S3 Permission Issues
```bash
# Check bucket policy
aws s3api get-bucket-policy --bucket your-bucket-name

# Test S3 access
aws s3 ls s3://your-bucket-name/
```

### No Data in S3
```bash
# Check Lambda logs for errors
aws logs tail /aws/lambda/stock-data-fetcher --since 1h

# Invoke Lambda manually to test
aws lambda invoke --function-name stock-data-fetcher output.json
```

### Yahoo Finance Rate Limiting
If you see 429 errors:
1. The Lambda timeout is set to 15 minutes to handle this automatically
2. yfinance has built-in rate limiting protection (waits 15 minutes on 429)
3. Default 2-second delay between symbols is already configured
4. If still hitting limits, reduce symbols per execution to <30
5. Consider splitting symbol list across multiple time windows

## Next Steps

1. **Customize Strategies**: Create your own trading strategies in `modules/backtesting/strategies/`
2. **Add Indicators**: Implement custom technical indicators in `modules/indicators/`
3. **Optimize**: Run parameter optimization for your strategies
4. **Visualize**: Create charts and dashboards for backtest results
5. **Automate**: Set up CI/CD pipeline for automated testing and deployment

## Getting Help

- **Documentation**: See [README.md](README.md) for detailed information
- **API Reference**: See [API_SPECIFICATION.md](API_SPECIFICATION.md)
- **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Issues**: Open an issue on GitHub
- **Discussions**: Join GitHub Discussions

## Clean Up (Optional)

To remove all AWS resources and avoid charges:

```bash
# Destroy infrastructure
cd terraform
terraform destroy -auto-approve

# Delete S3 bucket (if not empty)
aws s3 rb s3://your-bucket-name --force

# Remove local data
rm -rf data/ .cache/
```

---

**Congratulations!** 🎉 You've successfully set up Stock Stream 2.
