# Step Functions Architecture

## Overview

Stock Stream 2 uses AWS Step Functions to orchestrate a daily data pipeline that fetches stock data for all ASX-listed companies. The pipeline consists of two main steps:

1. **ASX Symbol Updater** - Fetches and exports the list of ASX-listed stocks
2. **Parallel Stock Data Fetcher** - Fetches stock data in batches of 100 symbols

This architecture enables parallel processing of 1000+ symbols in ~5 minutes while respecting rate limits and providing fault isolation.

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        Daily Pipeline                           │
└────────────────────────────────────────────────────────────────┘

EventBridge (Cron: Daily at 6:00 AM AEST)
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step Functions State Machine: stock-data-pipeline               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 1: UpdateASXSymbols (Task)                         │    │
│  │                                                          │    │
│  │  Lambda: asx-symbol-updater                             │    │
│  │  - Fetch ASX-listed companies from ASX website          │    │
│  │  - Export to S3: symbols/YYYY-MM-DD-symbols.csv         │    │
│  │  - Split into batches of 100 symbols                    │    │
│  │  - Return symbolBatches array                           │    │
│  │                                                          │    │
│  │  Output:                                                 │    │
│  │  {                                                       │    │
│  │    "symbols": ["BHP", "CBA", ...],                      │    │
│  │    "symbolBatches": [                                   │    │
│  │      {"symbols": [...], "batchNumber": 0},              │    │
│  │      {"symbols": [...], "batchNumber": 1},              │    │
│  │      ...                                                 │    │
│  │    ],                                                    │    │
│  │    "metadata": { "total_symbols": 2147, ... }           │    │
│  │  }                                                       │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                        │
│                         ↓                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 2: SplitIntoBatches (Map State)                    │    │
│  │                                                          │    │
│  │  MaxConcurrency: 10                                     │    │
│  │  ItemsPath: $.symbolBatches                             │    │
│  │                                                          │    │
│  │  For each batch:                                        │    │
│  │    ┌─────────────────────────────────────────────┐      │    │
│  │    │ Lambda: stock-data-fetcher                  │      │    │
│  │    │                                              │      │    │
│  │    │ Input: {                                    │      │    │
│  │    │   "symbols": [...100 symbols...],           │      │    │
│  │    │   "batchNumber": N                          │      │    │
│  │    │ }                                            │      │    │
│  │    │                                              │      │    │
│  │    │ Process:                                    │      │    │
│  │    │ 1. Fetch data from Yahoo Finance            │      │    │
│  │    │ 2. 2-second delay between symbols           │      │    │
│  │    │ 3. Convert to Polars DataFrame              │      │    │
│  │    │ 4. Save to S3 as Parquet                    │      │    │
│  │    │                                              │      │    │
│  │    │ Output: raw-data/YYYY-MM-DD-batch-N.parquet │      │    │
│  │    └─────────────────────────────────────────────┘      │    │
│  │                                                          │    │
│  │    ┌─────────────────────────────────────────────┐      │    │
│  │    │ Lambda: stock-data-fetcher (Batch 1)        │      │    │
│  │    └─────────────────────────────────────────────┘      │    │
│  │                                                          │    │
│  │    ... (up to 10 concurrent instances) ...              │    │
│  │                                                          │    │
│  │    ┌─────────────────────────────────────────────┐      │    │
│  │    │ Lambda: stock-data-fetcher (Batch N)        │      │    │
│  │    └─────────────────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         │                                        │
│                         ↓                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Step 3: AggregateResults (Pass State)                   │    │
│  │                                                          │    │
│  │  Collects results from all batches                      │    │
│  │  Output: Summary of successful/failed batches           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
    ↓
S3 Bucket Structure:
├── symbols/
│   └── 2025-12-26-symbols.csv
└── raw-data/
    ├── 2025-12-26-batch-0.parquet
    ├── 2025-12-26-batch-1.parquet
    ├── 2025-12-26-batch-2.parquet
    └── ...
```

## Component Details

### 1. EventBridge Rule

**Trigger Schedule:** Daily at 6:00 AM AEST (Australian Eastern Standard Time)

**Cron Expression:** `cron(0 20 * * ? *)` (UTC time)

**Target:** Step Functions State Machine

**Purpose:** Initiates the daily pipeline automatically

### 2. Lambda: ASX Symbol Updater

**Function Name:** `asx-symbol-updater`

**Runtime:** Python 3.12

**Memory:** 256 MB

**Timeout:** 5 minutes

**Responsibilities:**
- Fetch list of ASX-listed companies from ASX website/API
- Parse and validate company data
- Export to CSV: `s3://bucket/symbols/YYYY-MM-DD-symbols.csv`
- Split symbols into batches of 100
- Return structured output for Step Functions

**Output Format:**
```json
{
  "statusCode": 200,
  "symbols": ["BHP", "CBA", "NAB", ...],
  "symbolBatches": [
    {
      "symbols": ["BHP", "CBA", "NAB", ...],
      "batchNumber": 0
    },
    {
      "symbols": ["WBC", "ANZ", "CSL", ...],
      "batchNumber": 1
    }
  ],
  "metadata": {
    "total_symbols": 2147,
    "num_batches": 22,
    "s3_key": "symbols/2025-12-26-symbols.csv",
    "changes": {
      "added": ["NEW1", "NEW2"],
      "removed": ["OLD1"]
    }
  }
}
```

### 3. Lambda: Stock Data Fetcher

**Function Name:** `stock-data-fetcher`

**Runtime:** Python 3.12

**Memory:** 512 MB

**Timeout:** 15 minutes

**Concurrency:** Up to 10 instances in parallel

**Responsibilities:**
- Receive batch of up to 100 symbols from Step Functions
- Fetch OHLCV data from Yahoo Finance for each symbol
- Apply 2-second delay between requests (rate limiting)
- Validate and clean data
- Convert to Polars DataFrame
- Export to Parquet: `s3://bucket/raw-data/YYYY-MM-DD-batch-N.parquet`

**Input Format:**
```json
{
  "symbols": ["BHP", "CBA", ...],
  "batchNumber": 0,
  "date": "2025-12-26"
}
```

**Output Format:**
```json
{
  "statusCode": 200,
  "body": "...",
  "metadata": {
    "batch_number": 0,
    "symbols_processed": 100,
    "symbols_fetched": 98,
    "symbols_failed": ["XYZ", "ABC"],
    "execution_time": 215.3,
    "s3_key": "raw-data/2025-12-26-batch-0.parquet"
  }
}
```

**Parquet Schema:**
| Column | Type | Description |
|--------|------|-------------|
| symbol | string | Stock ticker symbol |
| date | date | Trading date |
| open | float64 | Opening price |
| high | float64 | Highest price |
| low | float64 | Lowest price |
| close | float64 | Closing price |
| volume | int64 | Trading volume |
| adjusted_close | float64 | Split/dividend adjusted close |
| fetch_timestamp | string | ISO 8601 timestamp |
| batch_number | int32 | Batch identifier |

### 4. Step Functions State Machine

**State Machine Name:** `stock-data-pipeline`

**IAM Role:** `StepFunctionsExecutionRole`

**States:**

#### State 1: UpdateASXSymbols (Task)
- **Type:** Task
- **Resource:** Lambda ARN (asx-symbol-updater)
- **Retry Strategy:**
  - Error: `States.TaskFailed`
  - Interval: 60 seconds
  - Max Attempts: 3
  - Backoff Rate: 2.0
- **Catch:**
  - All errors → NotifyFailure state
- **Next:** SplitIntoBatches

#### State 2: SplitIntoBatches (Map)
- **Type:** Map
- **ItemsPath:** `$.symbolBatches`
- **MaxConcurrency:** 10
- **Iterator:**
  - FetchStockData (Task)
    - Resource: Lambda ARN (stock-data-fetcher)
    - Retry: 2 attempts with 30s interval
    - Catch: Continue on error (fault isolation)
- **ResultPath:** `$.batchResults`
- **Next:** AggregateResults

#### State 3: AggregateResults (Pass)
- **Type:** Pass
- **Comment:** Collect and summarize batch results
- **End:** true

#### State 4: NotifyFailure (SNS)
- **Type:** Task
- **Resource:** SNS Publish ARN
- **Parameters:**
  - TopicArn: `stock-stream-alerts`
  - Subject: "Stock Stream Pipeline Failed"
  - Message: Error details
- **End:** true

## Execution Flow

### Normal Execution

```
1. EventBridge triggers Step Functions at 6:00 AM
2. Step Functions invokes asx-symbol-updater Lambda
3. Lambda fetches 2147 ASX symbols
4. Lambda splits into 22 batches of 100 symbols each
5. Lambda returns symbolBatches array
6. Step Functions Map state processes batches:
   - Batch 0-9: Processed concurrently (first wave)
   - Batch 10-19: Processed concurrently (second wave)
   - Batch 20-21: Processed concurrently (third wave)
7. Each Lambda instance:
   - Fetches data for its 100 symbols (3-4 minutes)
   - Saves to S3 as batch-N.parquet
8. Step Functions collects all results
9. Execution completes successfully
```

**Total Time:** ~6-8 minutes for 2200 symbols

### Error Handling

**Scenario 1: ASX Symbol Updater Fails**
- Step Functions retries 3 times with exponential backoff
- If all retries fail, transitions to NotifyFailure state
- SNS notification sent to administrators
- Entire pipeline halts (no stock data fetch without symbols)

**Scenario 2: Single Batch Fails**
- Lambda retries 2 times automatically
- If still fails, batch is marked as failed
- Other batches continue processing (fault isolation)
- Failed batch logged in CloudWatch
- Pipeline completes with partial success

**Scenario 3: Multiple Batches Fail**
- Each batch handled independently
- Successful batches saved to S3
- Failed batches logged separately
- Pipeline completes with partial results
- Data aggregator handles missing batches gracefully

## Performance Characteristics

### Timing Analysis

| Symbols | Batches | Waves (Concurrent=10) | Time |
|---------|---------|----------------------|------|
| 100 | 1 | 1 | ~4 min |
| 500 | 5 | 1 | ~4 min |
| 1000 | 10 | 1 | ~4 min |
| 2000 | 20 | 2 | ~8 min |
| 2200 | 22 | 3 | ~12 min |

**Formula:** Time ≈ (num_batches / max_concurrency) × batch_time

**Single Batch Time Breakdown:**
- Lambda cold start: 2-5 seconds
- Initialize Yahoo Finance: 1-2 seconds
- Fetch 100 symbols (2s delay each): 200 seconds
- Data processing: 5-10 seconds
- S3 upload: 2-5 seconds
- **Total:** ~210-220 seconds (3.5-4 minutes)

### Resource Utilization

**Lambda Invocations per Day:**
- ASX Symbol Updater: 1
- Stock Data Fetcher: 22 (for 2200 symbols)
- **Total:** 23 invocations

**Lambda Execution Time:**
- ASX Symbol Updater: ~1 minute
- Stock Data Fetcher: 22 × 4 min = 88 minutes
- **Total:** 89 minutes

**Lambda GB-seconds:**
- ASX Symbol Updater: 0.25 GB × 1 min = 0.25 GB-min
- Stock Data Fetcher: 0.5 GB × 88 min = 44 GB-min
- **Total:** 44.25 GB-min ≈ 2655 GB-seconds

**Step Functions State Transitions:**
- Start → UpdateASXSymbols: 1
- UpdateASXSymbols → SplitIntoBatches: 1
- Map iterations: 22
- Map results: 22
- AggregateResults → End: 1
- **Total:** ~47 transitions

### Cost Estimation (Daily)

| Service | Usage | Rate | Cost |
|---------|-------|------|------|
| Lambda Requests | 23 | $0.20 per 1M | $0.0000046 |
| Lambda Duration | 2655 GB-sec | $0.0000166667 per GB-sec | $0.044 |
| Step Functions | 47 transitions | $0.025 per 1000 | $0.0012 |
| S3 PUT | 23 | $0.005 per 1000 | $0.0001 |
| S3 Storage | ~50 MB | $0.023 per GB/month | $0.0012 |
| **Daily Total** | | | **$0.047** |
| **Monthly Total** | | | **$1.41** |
| **Annual Total** | | | **$17.15** |

**Note:** Costs may vary based on actual execution time and data volume.

## Monitoring and Alerts

### CloudWatch Metrics

**Step Functions:**
- ExecutionTime
- ExecutionsSucceeded
- ExecutionsFailed
- ExecutionsTimedOut

**Lambda (per function):**
- Invocations
- Duration
- Errors
- Throttles
- ConcurrentExecutions

**Custom Metrics:**
- SymbolsFetched
- SymbolsFailed
- BatchesProcessed
- BatchesFailed

### CloudWatch Alarms

1. **Pipeline Execution Failed**
   - Metric: ExecutionsFailed
   - Threshold: ≥ 1
   - Action: SNS notification

2. **High Lambda Error Rate**
   - Metric: Errors / Invocations
   - Threshold: > 10%
   - Action: SNS notification

3. **Lambda Timeout**
   - Metric: Duration
   - Threshold: > 14 minutes (near timeout)
   - Action: SNS notification

4. **Low Symbol Fetch Rate**
   - Metric: SymbolsFetched / TotalSymbols
   - Threshold: < 90%
   - Action: SNS notification

### CloudWatch Dashboards

**Dashboard: Stock Data Pipeline**

Widgets:
1. Step Functions execution status (success/fail)
2. Lambda invocations and duration (both functions)
3. Symbols fetched vs. failed (pie chart)
4. Batch processing time (line chart)
5. S3 storage utilization (trend)
6. Cost per execution (calculated)

## Advantages of This Architecture

### 1. Parallel Processing
- Process 1000+ symbols in ~4 minutes (vs. 33 minutes sequentially)
- Max 10 concurrent Lambda instances
- Automatic load balancing

### 2. Fault Isolation
- Single batch failure doesn't affect other batches
- Data from successful batches preserved
- Easy to re-run failed batches independently

### 3. Scalability
- Add more symbols without code changes
- Increase MaxConcurrency for faster processing
- No infrastructure management required

### 4. Cost Efficiency
- Pay only for execution time (~$1.41/month)
- No idle server costs
- Automatic scaling (no over-provisioning)

### 5. Maintainability
- Clear separation of concerns (2 Lambda functions)
- Visual workflow in Step Functions console
- Easy to debug and monitor
- Simple to add new steps (e.g., data quality checks)

### 6. Reliability
- Automatic retries with exponential backoff
- Built-in error handling
- CloudWatch logging for troubleshooting
- SNS notifications on failures

## Data Aggregator Integration

The Data Aggregator module seamlessly handles the batch file structure:

```python
from modules.data_aggregator import DataAggregator

# Initialize aggregator
aggregator = DataAggregator(bucket="stock-stream-data")

# Load all data for a specific date
# Automatically discovers and merges all batch files
df = aggregator.load_date("2025-12-26")

# Load date range
# Merges batches across multiple dates
df = aggregator.load_date_range("2025-12-01", "2025-12-31")

# Load specific symbols
# Scans all batch files to find matching symbols
df = aggregator.load_symbols(["BHP", "CBA", "NAB"])
```

**Batch Merging Logic:**
1. List all files in S3 for the date: `2025-12-26-batch-*.parquet`
2. Load each batch into Polars DataFrame
3. Concatenate all batches vertically
4. Remove duplicates (if any)
5. Return unified DataFrame

## Future Enhancements

### 1. Dynamic Batch Sizing
- Adjust batch size based on rate limit headroom
- Larger batches when rate limits allow
- Smaller batches during high-load periods

### 2. Intelligent Retry
- Skip symbols that consistently fail
- Exponential backoff per symbol (not per batch)
- Separate retry queue for failed symbols

### 3. Data Quality Checks
- Add validation step after batch processing
- Check for missing symbols, outliers, data gaps
- Alert on quality issues before downstream processing

### 4. Incremental Updates
- Only fetch symbols that have changed
- Compare with previous day's data
- Skip unchanged symbols to save time

### 5. Multi-Region Deployment
- Deploy pipeline in multiple AWS regions
- Distribute symbol batches across regions
- Reduce rate limiting impact

### 6. Real-Time Processing
- Add intraday data fetching (hourly/minute-level)
- Stream data to Kinesis for real-time analysis
- Support live trading strategies

## Conclusion

The Step Functions-based architecture provides a robust, scalable, and cost-effective solution for fetching daily stock data. By processing symbols in parallel batches, the system can handle 1000+ stocks in minutes while maintaining fault isolation and respecting rate limits. The architecture is production-ready and easily extensible for future requirements.
