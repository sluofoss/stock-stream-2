# Local Testing Setup - Complete Guide

This guide walks you through setting up your local development environment and testing Stock Stream 2 modules without requiring AWS access.

## Quick Start (5 minutes)

### Prerequisites
- Python 3.12+
- `uv` package manager ([Install here](https://github.com/astral-sh/uv))
- Git

### Step 1: Clone and Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd stock-stream-2

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows
```

### Step 2: Install Dependencies

```bash
# Install core dependencies (required)
uv pip install polars pyarrow boto3 yfinance requests beautifulsoup4 python-dotenv loguru

# Install development dependencies (optional, for testing/linting)
uv pip install pytest pytest-cov pytest-mock mypy ruff black moto
```

Expected output:
```
Resolved 33 packages in 100ms
Installed 33 packages in 287ms
```

### Step 3: Test Locally

```bash
# Run ASX Symbol Updater with mock data
python scripts/run_asx_updater_local.py
```

**Expected Output:**
```
================================================================================
ASX Symbol Updater - Local Test Mode
================================================================================

Running with mock data (no AWS S3 access required)

2025-12-26 19:29:57 | INFO     | modules.asx_symbol_updater.handler:lambda_handler:392 - ASX Symbol Updater started
...

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

### Success Indicators

If you see `✅ SUCCESS`, your environment is correctly set up! This confirms:
- ✅ Python environment configured
- ✅ All dependencies installed
- ✅ Module imports working
- ✅ Logger configured
- ✅ Step Functions output format correct

## What is Mock Mode?

**Mock Mode** allows you to test Lambda functions locally without AWS credentials or network access.

### How it Works

When `USE_MOCK_DATA=true` environment variable is set:
- **ASX Symbol Updater:** Returns 10 hardcoded stock symbols instead of web scraping
- **S3 Operations:** Print log messages instead of actual uploads/downloads
- **Output:** Same JSON format as production for Step Functions compatibility

### When to Use Mock Mode

✅ **Use Mock Mode For:**
- Initial environment setup verification
- Testing module logic and data transformations
- Debugging without AWS costs
- CI/CD pipelines without AWS access
- Learning the codebase

❌ **Don't Use Mock Mode For:**
- Testing actual web scraping behavior
- Validating S3 bucket configurations
- Performance benchmarking
- Integration testing

## Testing Other Modules

### Stock Data Fetcher (Coming Soon)

Once implemented, you'll be able to test it similarly:

```bash
python scripts/run_stock_fetcher_local.py
```

## Advanced Testing

### Option 1: Direct Module Execution

```bash
# Set mock mode
export USE_MOCK_DATA=true

# Run module directly
python -m modules.asx_symbol_updater.handler
```

### Option 2: Interactive Python

```python
import os
os.environ['USE_MOCK_DATA'] = 'true'

from modules.asx_symbol_updater.handler import lambda_handler

# Test with mock event
event = {}
context = type('obj', (object,), {
    'function_name': 'test',
    'function_version': '1',
    'invoked_function_arn': 'arn:aws:lambda:test',
    'memory_limit_in_mb': 256,
    'aws_request_id': 'test-request-id'
})()

result = lambda_handler(event, context)
print(result)
```

### Option 3: Test Runner Script (Recommended)

The test runner provides formatted output with clear success/failure indicators:

```bash
python scripts/run_asx_updater_local.py
```

## Testing with Real AWS S3

To test with actual AWS services:

### 1. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region: ap-southeast-2
```

### 2. Set Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=ap-southeast-2
USE_MOCK_DATA=false
EOF
```

### 3. Ensure S3 Bucket Exists

```bash
aws s3 mb s3://your-bucket-name --region ap-southeast-2
```

### 4. Run Without Mock Mode

```bash
# Disable mock mode
export USE_MOCK_DATA=false

# Run test
python scripts/run_asx_updater_local.py
```

**Expected Behavior:**
- Downloads actual ASX company list from website
- Uploads CSV to S3 bucket
- Downloads CSV from S3
- Splits into batches
- Returns batch information

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'polars'`

**Solution:** Dependencies not installed
```bash
source .venv/bin/activate
uv pip install polars pyarrow boto3 yfinance requests beautifulsoup4 python-dotenv loguru
```

### Issue: `ImportError: cannot import name 'get_logger'`

**Solution:** Old code using deprecated logger function
- **Fixed in:** All modules now use `from loguru import logger`
- **Action:** Pull latest code from repository

### Issue: `ClientError: An error occurred (NoSuchBucket) when calling the PutObject operation`

**Solution:** S3 bucket doesn't exist or incorrect name
```bash
# Check bucket name in environment
echo $S3_BUCKET_NAME

# Create bucket if needed
aws s3 mb s3://your-bucket-name --region ap-southeast-2
```

### Issue: Mock mode output but expected real data

**Solution:** Mock mode still enabled
```bash
# Check environment variable
echo $USE_MOCK_DATA

# Disable mock mode
export USE_MOCK_DATA=false
# or
unset USE_MOCK_DATA
```

## Next Steps

After confirming local setup works:

1. **Write Unit Tests:** Create tests in `tests/unit/`
2. **Deploy to AWS:** Follow [QUICK_START.md](QUICK_START.md) deployment guide
3. **Configure Terraform:** Set up infrastructure in `terraform/`
4. **Test End-to-End:** Run full Step Functions pipeline in AWS

## Additional Resources

- [Quick Start Guide](QUICK_START.md) - Full deployment guide
- [Contributing Guide](../CONTRIBUTING.md) - Development workflow
- [Module README](../modules/asx_symbol_updater/README.md) - ASX Symbol Updater details
- [API Specification](API_SPECIFICATION.md) - Lambda function contracts
- [Logging Guide](LOGGING_GUIDE.md) - Logger configuration details

## Feedback

If you encounter issues not covered here, please:
1. Check existing GitHub issues
2. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Open a new issue with:
   - Python version (`python --version`)
   - Operating system
   - Full error message
   - Steps to reproduce
