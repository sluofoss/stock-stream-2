# ASX Symbol Updater Module

AWS Lambda function that fetches and maintains the list of ASX-listed companies.

## Overview

This Lambda function is the first step in the Stock Stream 2 pipeline. It:

1. **Downloads CSV** from ASX website directory
2. **Uploads to S3** with date-stamped filename
3. **Retrieves latest file** from S3 (validates upload)
4. **Splits symbols** into batches of 100
5. **Returns output** formatted for Step Functions

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         ASX Symbol Updater Lambda                   │
├─────────────────────────────────────────────────────┤
│                                                       │
│  1. Download CSV from ASX Website                    │
│     https://www.asx.com.au/markets/...               │
│     ↓                                                 │
│  2. Parse CSV (symbol, name, sector, market_cap)     │
│     ↓                                                 │
│  3. Upload to S3                                      │
│     s3://bucket/symbols/YYYY-MM-DD-symbols.csv       │
│     ↓                                                 │
│  4. Retrieve Latest from S3 (validation)             │
│     ↓                                                 │
│  5. Split into Batches                                │
│     [batch-0: symbols 0-99]                          │
│     [batch-1: symbols 100-199]                       │
│     ...                                               │
│     ↓                                                 │
│  6. Return to Step Functions                         │
│     {symbols: [...], symbolBatches: [...]}           │
│                                                       │
└─────────────────────────────────────────────────────┘
```

## Input

### Event Format
```json
{
  "date": "2025-12-26"  // Optional: override date (for testing)
}
```

Typically invoked by Step Functions with an empty event `{}`.

### Environment Variables
- `S3_BUCKET` (required): S3 bucket name for storing symbols
- `LOG_LEVEL` (optional): Logging level (default: INFO)

## Output

### Success Response
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

### Error Response
```json
{
  "statusCode": 500,
  "body": "{...}",
  "metadata": {
    "request_id": "abc-123",
    "timestamp": "2025-12-26T00:00:00Z",
    "error": "ASXSymbolUpdaterError"
  }
}
```

## S3 Storage Structure

```
s3://bucket-name/
└── symbols/
    ├── 2025-12-26-symbols.csv
    ├── 2025-12-25-symbols.csv
    ├── 2025-12-24-symbols.csv
    └── ...
```

Each file contains the full snapshot of ASX-listed companies for that date.

## CSV Format

The CSV downloaded from ASX typically has columns:
- `ASX code` or `Symbol`: Stock ticker (e.g., "BHP")
- `Company name` or `Name`: Company name (e.g., "BHP Group Limited")
- `GICS industry group` or `Sector`: Industry sector
- `Market Cap`: Market capitalization (optional)

Example:
```csv
symbol,name,sector,market_cap
BHP,BHP Group Limited,Materials,180500000000
CBA,Commonwealth Bank,Financials,165200000000
NAB,National Australia Bank,Financials,98450000000
```

## Implementation Details

### CSV Download Process

The function scrapes the ASX directory page to find the CSV download link:

```python
# 1. Fetch directory page HTML
response = requests.get("https://www.asx.com.au/markets/trade-our-cash-market/directory")

# 2. Parse HTML with BeautifulSoup
soup = BeautifulSoup(response.text, 'html.parser')

# 3. Find CSV download link (text contains "CSV download")
csv_link = soup.find('a', string=lambda text: text and 'CSV download' in text)

# 4. Extract URL from onclick or href attribute
csv_url = extract_csv_download_url(csv_link)

# 5. Download CSV
csv_content = requests.get(csv_url).text
```

### Flexible CSV Parsing

The parser handles various column name formats used by ASX:

```python
symbol = row.get('ASX code') or row.get('Code') or row.get('Symbol')
name = row.get('Company name') or row.get('Name') or row.get('Company')
sector = row.get('GICS industry group') or row.get('Industry') or row.get('Sector')
```

This ensures compatibility even if ASX changes their CSV format.

### Batch Splitting

Symbols are split into fixed-size batches:

```python
BATCH_SIZE = 100

batches = []
for i in range(0, len(symbols), BATCH_SIZE):
    batch_symbols = symbols[i:i + BATCH_SIZE]
    batches.append({
        "symbols": batch_symbols,
        "batchNumber": i // BATCH_SIZE
    })
```

**Example:**
- 2147 symbols → 22 batches
- Batch 0: symbols 0-99 (100 symbols)
- Batch 1: symbols 100-199 (100 symbols)
- ...
- Batch 21: symbols 2100-2146 (47 symbols)

## Error Handling

### Errors Raised

1. **ASXSymbolUpdaterError**: Custom exception for all module-specific errors
2. **RequestException**: Network/HTTP errors during download
3. **ValueError**: CSV parsing errors

### Retry Strategy

The Lambda has built-in retries at multiple levels:

1. **Step Functions Level**: 3 retries with exponential backoff
2. **Application Level**: Graceful error handling and logging
3. **Network Level**: requests library timeout and retry logic

### Common Failures

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV download link not found | ASX website structure changed | Update `extract_csv_download_url()` logic |
| No companies parsed | CSV format changed | Update column name mappings |
| S3 upload failed | Permissions or bucket issue | Check IAM role and S3 bucket |
| Timeout | Network slow or large file | Increase Lambda timeout |

## Performance

### Typical Execution
- **Duration**: 30-60 seconds
- **Memory**: 128-256 MB used (256 MB allocated)
- **Cost**: ~$0.0001 per invocation

### Timing Breakdown
- Download CSV: 10-20 seconds
- Parse CSV: 1-2 seconds
- Upload to S3: 1-2 seconds
- Retrieve from S3: 1-2 seconds
- Split into batches: <1 second

## Lambda Configuration

### Recommended Settings
```yaml
Function Name: asx-symbol-updater
Runtime: Python 3.12
Memory: 256 MB
Timeout: 5 minutes (300 seconds)
Environment Variables:
  - S3_BUCKET: stock-stream-data
  - LOG_LEVEL: INFO
```

### IAM Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::bucket-name/*",
        "arn:aws:s3:::bucket-name"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### VPC Configuration
Not required. The function needs internet access to reach the ASX website.

## Testing

### Environment Setup

First, set up the development environment:

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install polars pyarrow boto3 yfinance requests beautifulsoup4 python-dotenv loguru
```

### Local Testing

**Option 1: Using the test runner script (Recommended)**

```bash
# Run with mock data (no AWS credentials required)
python scripts/run_asx_updater_local.py
```

This script:
- Sets `USE_MOCK_DATA=true` to use mock ASX data
- Sets `S3_BUCKET=stock-stream-test` 
- Runs the handler with a mock Lambda context
- Provides formatted output showing execution results

**Option 2: Direct module execution**

```bash
# The handler has a built-in test mode
export S3_BUCKET=stock-stream-test
python -m modules.asx_symbol_updater.handler
```

**Option 3: Python script**

```python
import os
os.environ["S3_BUCKET"] = "stock-stream-test"
os.environ["USE_MOCK_DATA"] = "true"

from modules.asx_symbol_updater.handler import lambda_handler

class MockContext:
    request_id = "test-123"
    
result = lambda_handler({}, MockContext())
print(result)
```

### Mock Mode

When `USE_MOCK_DATA=true` environment variable is set, the module:
- Uses hardcoded sample ASX data (10 major stocks)
- Skips actual web scraping
- Skips S3 upload/download operations
- Returns properly formatted Step Functions output

This is perfect for:
- Local development
- Unit testing
- CI/CD pipelines
- Testing Step Functions integration without AWS

### Testing with Real ASX Website

To test with the actual ASX website (requires internet, no AWS needed for download):

```bash
export S3_BUCKET=stock-stream-test
export USE_MOCK_DATA=false  # or unset it
python -m modules.asx_symbol_updater.handler
```

**Note**: This will fail at S3 upload unless you have AWS credentials configured.

### Testing with Real AWS S3

To test the complete flow with actual S3:

### Testing with Real AWS S3

To test the complete flow with actual S3:

```bash
# 1. Configure AWS credentials
aws configure

# 2. Create S3 bucket (if needed)
aws s3 mb s3://stock-stream-test

# 3. Run without mock mode
export S3_BUCKET=stock-stream-test
unset USE_MOCK_DATA
python -m modules.asx_symbol_updater.handler
```

This will:
- Download actual CSV from ASX website
- Upload to your S3 bucket
- Retrieve from S3 to validate
- Return real symbol data

### Unit Testing

```python
import pytest
from modules.asx_symbol_updater.handler import (
    parse_asx_csv,
    split_into_batches,
    extract_csv_download_url
)

def test_parse_csv():
    csv_content = """symbol,name,sector,market_cap
BHP,BHP Group Limited,Materials,180500000000
CBA,Commonwealth Bank,Financials,165200000000"""
    
    companies = parse_asx_csv(csv_content)
    assert len(companies) == 2
    assert companies[0]['symbol'] == 'BHP'

def test_batch_splitting():
    symbols = [f"SYM{i}" for i in range(250)]
    batches = split_into_batches(symbols, batch_size=100)
    
    assert len(batches) == 3
    assert len(batches[0]['symbols']) == 100
    assert len(batches[1]['symbols']) == 100
    assert len(batches[2]['symbols']) == 50
    assert batches[0]['batchNumber'] == 0
    assert batches[2]['batchNumber'] == 2
```

### Integration Testing with moto

```python
import boto3
from moto import mock_s3
from modules.asx_symbol_updater.handler import lambda_handler

@mock_s3
def test_lambda_handler():
    # Setup mock S3
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='test-bucket')
    
    # Mock context
    class MockContext:
        request_id = "test-123"
    
    # Test (will fail on ASX website access, but tests S3 logic)
    event = {}
    # ... test implementation
```

## Monitoring

### CloudWatch Metrics
- **Invocations**: Number of executions
- **Duration**: Execution time
- **Errors**: Failed executions
- **Throttles**: Rate limit hits

### Custom Logs
```
[INFO] ASX Symbol Updater started
[INFO] Step 1: Downloading ASX CSV from website
[INFO] Found CSV download URL: https://...
[INFO] Successfully downloaded ASX CSV (size_bytes=245678)
[INFO] Parsed 2147 companies from CSV
[INFO] Step 2: Uploading CSV to S3
[INFO] Successfully uploaded to S3 (key=symbols/2025-12-26-symbols.csv)
[INFO] Step 3: Retrieving latest symbols from S3
[INFO] Latest symbols file: symbols/2025-12-26-symbols.csv
[INFO] Step 4: Splitting symbols into batches
[INFO] Split 2147 symbols into 22 batches
[INFO] ASX Symbol Updater completed successfully (execution_time=45.3s)
```

### Alerts
Set up CloudWatch Alarms for:
- Execution errors (> 0)
- Duration > 4 minutes (approaching timeout)
- Invocation failures (Step Functions retries exhausted)

## Dependencies

Dependencies are managed in the root `pyproject.toml`:
- `boto3>=1.34.0` - AWS SDK
- `requests>=2.31.0` - HTTP client
- `beautifulsoup4>=4.12.0` - HTML parsing

Also uses common modules:
- `modules.common.logger`
- `modules.common.exceptions`

To install all dependencies:
```bash
uv pip install -e ".[dev]"
```

## Future Enhancements

### 1. Change Detection
Track changes between daily snapshots:
```python
def detect_changes(previous_symbols, current_symbols):
    added = set(current_symbols) - set(previous_symbols)
    removed = set(previous_symbols) - set(current_symbols)
    return {"added": list(added), "removed": list(removed)}
```

### 2. SNS Notifications
Alert on significant changes:
```python
if len(added) > 10 or len(removed) > 10:
    sns.publish(
        TopicArn=ALERT_TOPIC,
        Subject="ASX Symbol List Changes",
        Message=f"Added: {len(added)}, Removed: {len(removed)}"
    )
```

### 3. Metadata Enrichment
Add more company details:
- Market capitalization ranges
- Industry classifications
- Listing dates
- Trading status

### 4. Alternative Data Sources
Add fallback data sources:
- ASX API (if available)
- Third-party financial data providers
- Cached previous day's data

### 5. Validation Rules
Add data quality checks:
- Symbol format validation (3-5 uppercase letters)
- Duplicate detection
- Missing data handling
- Suspicious market cap values

## Troubleshooting

### "CSV download link not found"
**Cause**: ASX website structure changed

**Solution**:
1. Visit https://www.asx.com.au/markets/trade-our-cash-market/directory
2. Inspect the CSV download button/link
3. Update `extract_csv_download_url()` function with new selectors

### "No companies found in CSV"
**Cause**: CSV format changed or empty response

**Solution**:
1. Download CSV manually and inspect format
2. Update column name mappings in `parse_asx_csv()`
3. Check if ASX changed their CSV structure

### "S3 upload failed"
**Cause**: Permissions or bucket doesn't exist

**Solution**:
1. Verify S3 bucket exists
2. Check Lambda IAM role has S3 permissions
3. Verify S3_BUCKET environment variable is correct

### Timeout (300 seconds exceeded)
**Cause**: Network slow or ASX website unresponsive

**Solution**:
1. Check ASX website is accessible
2. Increase timeout if consistently slow
3. Add retry logic for download step

## Contributing

When modifying this module:

1. **Test locally** with different CSV formats
2. **Update tests** for new functionality
3. **Update documentation** for API changes
4. **Handle errors gracefully** - don't let website changes break pipeline
5. **Log verbosely** - helps debug production issues

## License

See main project LICENSE file.
