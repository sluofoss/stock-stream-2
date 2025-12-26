# Mock System Documentation

## Overview

The ASX Symbol Updater now supports **two independent mock modes** that can be combined for flexible local testing:

1. **MOCK_ASX_SOURCE** - Mock the ASX website data source
2. **MOCK_AWS** - Mock AWS S3 operations

This separation allows you to test different scenarios without requiring AWS credentials or making network requests.

## Environment Variables

### MOCK_ASX_SOURCE

Controls whether to use mock ASX data or scrape the real ASX website.

**Values:**
- `true` - Use hardcoded mock data (10 companies)
- `false` - Download from real ASX website (1986+ companies)

**When `MOCK_ASX_SOURCE=true`:**
- Returns 10 hardcoded companies (BHP, CBA, NAB, etc.)
- No network request to ASX website
- Instant execution
- Perfect for quick testing of logic

**When `MOCK_ASX_SOURCE=false`:**
- Downloads real CSV from https://www.asx.com.au/asx/research/ASXListedCompanies.csv
- Takes 1-2 seconds to complete
- Gets current list (1986 companies as of Dec 2025)
- Logs full company count and sample symbols

### MOCK_AWS

Controls whether to use mock AWS S3 operations or real S3.

**Values:**
- `true` - Skip S3 uploads/downloads (no AWS credentials needed)
- `false` - Use real S3 operations (requires AWS credentials)

**When `MOCK_AWS=true`:**
- S3 uploads are logged but not executed
- S3 downloads return the data already in memory
- No AWS credentials required
- No AWS costs

**When `MOCK_AWS=false`:**
- Real S3 put_object and get_object calls
- Requires valid AWS credentials
- Requires S3_BUCKET environment variable
- Incurs AWS costs (minimal)

## Usage Examples

### Example 1: Full Mock Mode (Default)

```bash
# Test with mock ASX data and mock AWS
python scripts/run_asx_updater_local.py
```

**Environment:**
- `MOCK_ASX_SOURCE=true` (10 companies)
- `MOCK_AWS=true` (no S3)

**Use Case:** Quick smoke test, development without network

**Output:**
```
✅ SUCCESS
  - Total Symbols: 10
  - Number of Batches: 1
  - Execution Time: 0.001s
```

### Example 2: Real ASX Scraping + Mock AWS

```bash
# Test real ASX website scraping without AWS
MOCK_ASX_SOURCE=false python scripts/run_asx_updater_local.py
```

**Environment:**
- `MOCK_ASX_SOURCE=false` (1986 companies)
- `MOCK_AWS=true` (no S3)

**Use Case:** Test ASX website integration, verify CSV parsing, see real data

**Output:**
```
✅ SUCCESS
  - Total Symbols: 1986
  - Number of Batches: 20
  - Execution Time: 0.129s
```

**Logs:**
```
INFO | Successfully downloaded ASX CSV (direct URL)
INFO | ASX CSV contains 1986 companies
INFO | Parsed 1986 companies from CSV
INFO | Downloaded and parsed 1986 companies
INFO | Mock AWS: Would upload to S3
INFO | Mock AWS: Using downloaded CSV data instead of S3 retrieval
INFO | Split 1986 symbols into 20 batches
```

### Example 3: Real ASX + Real AWS

```bash
# Test everything with real AWS S3
export S3_BUCKET=my-stock-data-bucket
MOCK_ASX_SOURCE=false MOCK_AWS=false python scripts/run_asx_updater_local.py
```

**Environment:**
- `MOCK_ASX_SOURCE=false` (1986 companies)
- `MOCK_AWS=false` (real S3)

**Requirements:**
- AWS credentials configured (`aws configure`)
- S3 bucket exists
- Proper IAM permissions

**Use Case:** End-to-end integration test before deployment

### Example 4: Mock ASX + Real AWS

```bash
# Test S3 integration with small mock dataset
export S3_BUCKET=my-stock-data-bucket
MOCK_ASX_SOURCE=true MOCK_AWS=false python scripts/run_asx_updater_local.py
```

**Environment:**
- `MOCK_ASX_SOURCE=true` (10 companies)
- `MOCK_AWS=false` (real S3)

**Use Case:** Test S3 permissions and connectivity without large dataset

## Test Scripts

### scripts/run_asx_updater_local.py

General purpose test runner with configurable modes.

**Features:**
- Shows configuration before execution
- Formatted output with success/failure indicators
- Lists all batches
- Respects environment variables

**Usage:**
```bash
# Default: Full mock
python scripts/run_asx_updater_local.py

# Real scraping
MOCK_ASX_SOURCE=false python scripts/run_asx_updater_local.py

# Real everything
S3_BUCKET=my-bucket MOCK_ASX_SOURCE=false MOCK_AWS=false python scripts/run_asx_updater_local.py
```

### scripts/run_asx_updater_real_scrape.py

Dedicated script for testing real ASX scraping with detailed output.

**Features:**
- Pre-configured for real scraping (MOCK_ASX_SOURCE=false)
- Shows first 20 symbols
- Shows batch ranges (first and last symbol in each batch)
- Exception handling with traceback

**Usage:**
```bash
python scripts/run_asx_updater_real_scrape.py
```

**Sample Output:**
```
First 20 Symbols (out of 1986):
   1. 14D
   2. 29M
   3. T3D
   ...
  20. AKG
  ... and 1966 more

Symbol Batches:
  - Batch 0: 100 symbols (14D ... AIQ)
  - Batch 1: 100 symbols (ATT ... AUG)
  ...
  - Batch 19: 86 symbols (WAK ... ZAG)
```

## Implementation Details

### Code Structure

The mock checks are placed at the beginning of each function:

```python
def download_asx_csv() -> str:
    # Check MOCK_ASX_SOURCE
    if os.getenv("MOCK_ASX_SOURCE") == "true":
        return mock_csv_data
    
    # Real implementation...
    download from ASX website

def upload_to_s3(csv_content, bucket, date) -> str:
    # Check MOCK_AWS
    if os.getenv("MOCK_AWS") == "true":
        logger.info("Mock AWS: Would upload to S3")
        return s3_key
    
    # Real implementation...
    boto3.client('s3').put_object(...)
```

### Data Flow with MOCK_AWS=true

When `MOCK_AWS=true` and `MOCK_ASX_SOURCE=false`:

1. **Step 1:** Download real CSV from ASX → Parse into `companies` list
2. **Step 2:** Mock S3 upload → Log only, return key
3. **Step 3:** Instead of downloading from S3, use the `companies` from Step 1
4. **Step 4:** Split real symbols into batches

This ensures the real downloaded data flows through the entire pipeline.

## Logging

All mock operations are clearly logged:

```python
# MOCK_ASX_SOURCE=true
logger.info("Using mock ASX data for local testing")

# MOCK_AWS=true (upload)
logger.info("Mock AWS: Would upload to S3", bucket=bucket, key=s3_key)

# MOCK_AWS=true (download)
logger.info("Mock AWS: Using downloaded CSV data instead of S3 retrieval")
```

## Testing Matrix

| MOCK_ASX_SOURCE | MOCK_AWS | Network | AWS Creds | Use Case |
|-----------------|----------|---------|-----------|----------|
| true | true | No | No | Quick smoke test |
| false | true | Yes | No | Test ASX scraping |
| true | false | No | Yes | Test S3 with small data |
| false | false | Yes | Yes | Full integration test |

## Benefits

1. **Flexibility:** Test each component independently
2. **Speed:** Full mock mode runs in < 1ms
3. **Cost:** No AWS costs in mock mode
4. **Development:** Work offline with mock ASX source
5. **Debugging:** Test real scraping without S3 complexity
6. **CI/CD:** Run tests in CI without AWS credentials

## Migration from Old System

**Old (single variable):**
```bash
USE_MOCK_DATA=true  # Mocked everything
```

**New (two variables):**
```bash
MOCK_ASX_SOURCE=true  # Mock ASX website
MOCK_AWS=true         # Mock AWS S3
```

**Equivalent:**
- `USE_MOCK_DATA=true` → `MOCK_ASX_SOURCE=true` + `MOCK_AWS=true`
- `USE_MOCK_DATA=false` → `MOCK_ASX_SOURCE=false` + `MOCK_AWS=false`

## Future Extensions

Possible additional mock modes:

- `MOCK_STEP_FUNCTIONS` - For testing orchestration
- `MOCK_EVENTBRIDGE` - For testing scheduling
- `MOCK_LAMBDA_CONTEXT` - For testing Lambda-specific features

## Troubleshooting

### Issue: Still seeing 10 symbols when MOCK_ASX_SOURCE=false

**Check:**
```bash
echo $MOCK_ASX_SOURCE  # Should be "false" not "true"
```

**Solution:**
```bash
export MOCK_ASX_SOURCE=false
python scripts/run_asx_updater_local.py
```

### Issue: S3 errors when MOCK_AWS=false

**Check:**
- AWS credentials: `aws sts get-caller-identity`
- S3 bucket exists: `aws s3 ls s3://your-bucket-name`
- Environment variable: `echo $S3_BUCKET`

**Solution:**
```bash
aws configure  # Set credentials
export S3_BUCKET=your-bucket-name
```

### Issue: Network timeout downloading ASX CSV

**Possible causes:**
- Network connectivity issue
- ASX website temporarily down
- Firewall blocking requests

**Solution:**
```bash
# Test direct download
curl https://www.asx.com.au/asx/research/ASXListedCompanies.csv

# Use mock mode if network unavailable
export MOCK_ASX_SOURCE=true
```
