# Technical Notes & Clarifications

## Critical Implementation Details

### 1. yfinance Rate Limiting

#### The Issue
yfinance has built-in rate limiting (~2000 requests/hour from Yahoo Finance). When rate limited, yfinance automatically waits 15 minutes before retrying.

#### Our Solution
```python
# Environment Configuration
YAHOO_FINANCE_TIMEOUT=900  # 15 minutes (not 30 seconds!)
YAHOO_FINANCE_RATE_LIMIT_DELAY=2  # 2 seconds between symbols
YAHOO_FINANCE_MAX_RETRIES=5
YAHOO_FINANCE_RETRY_DELAY=60  # Start at 60s for exponential backoff
```

#### Implementation Strategy
```python
import yfinance as yf
import time

def fetch_stock_data(symbols: list[str]) -> dict:
    """Fetch data with proper rate limiting."""
    results = {}
    
    for symbol in symbols:
        try:
            # yfinance handles rate limits internally
            data = yf.download(
                symbol,
                period="1d",
                progress=False,
                timeout=900  # 15 minutes
            )
            results[symbol] = data
            
            # Rate limit protection: 2 seconds between requests
            # This gives us ~30 symbols/minute, ~1800/hour (safe margin)
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            # yfinance already handled rate limits with internal waits
            continue
    
    return results
```

#### Lambda Configuration
- **Timeout:** 15 minutes (900 seconds) - CRITICAL for rate limiting
- **Memory:** 512 MB
- **Concurrency:** 1 (don't run multiple instances in parallel)
- **Retry:** 0 (Lambda-level retries disabled, handle internally)

#### Why 15 Minutes?
- yfinance waits 15 minutes when it hits a 429 error
- If Lambda times out at 5 minutes, the entire execution fails
- With 15-minute timeout, yfinance can wait and retry successfully
- For 100 symbols: 100 * 2s = 200s = 3.3 minutes (normal)
- For 100 symbols with 1 rate limit hit: 3.3m + 15m = 18.3m (exceeds timeout, but rare)

#### Best Practice
**Limit to 30-50 symbols per Lambda execution** to avoid timeout issues:
```json
{
  "symbols_batch_1": ["BHP", "CBA", "NAB", ...],  // 30 symbols
  "symbols_batch_2": ["WBC", "ANZ", "CSL", ...],  // 30 symbols
  "symbols_batch_3": ["WES", "WOW", "FMG", ...]   // 30 symbols
}
```

---

### 2. PyArrow vs fastparquet

#### The Decision: PyArrow ✅

#### Why PyArrow?

**1. Already Required**
```python
# Polars dependency tree
polars → pyarrow (required)

# So fastparquet doesn't save space:
polars + pyarrow = Base deployment
polars + pyarrow + fastparquet = Larger deployment
```

**2. Deployment Size Comparison**

| Package | Unoptimized | Optimized | Notes |
|---------|------------|-----------|-------|
| PyArrow | ~50 MB | ~15 MB | After removing tests/examples |
| fastparquet | ~8 MB | ~8 MB | Still need PyArrow for Polars |
| pandas (if needed) | ~40 MB | ~35 MB | fastparquet often needs this |

**Total Lambda Package:**
- **With PyArrow only:** ~15 MB (optimized)
- **With fastparquet:** ~15 MB (PyArrow) + ~8 MB (fastparquet) = ~23 MB

**3. Performance**
```python
# Benchmark (100k rows, 10 columns)
pyarrow.write_parquet():  0.8s
fastparquet.write():      3.2s  # 4x slower

pyarrow.read_parquet():   0.3s
fastparquet.read():       1.5s  # 5x slower
```

**4. Maintenance**
- **PyArrow:** Backed by Apache Arrow (very active, 200+ contributors)
- **fastparquet:** Smaller team, slower release cycle

**5. Ecosystem**
- AWS Athena: Uses PyArrow
- AWS Glue: Uses PyArrow
- Pandas 2.0+: Recommends PyArrow backend
- Polars: Built on PyArrow

#### Lambda Deployment Optimization

```bash
# Makefile target to optimize PyArrow
optimize-lambda-package:
	cd lambda_packages/stock_data_fetcher && \
	# Remove PyArrow bloat
	rm -rf pyarrow/tests/ && \
	rm -rf pyarrow/include/ && \
	rm -rf pyarrow/*.pyx && \
	# Remove all .pyc and __pycache__
	find . -type f -name "*.pyc" -delete && \
	find . -type d -name "__pycache__" -exec rm -rf {} + && \
	# Remove unnecessary files
	find . -type f -name "*.so.debug" -delete && \
	find . -type f -name "*.pyd" -delete && \
	# Strip binaries (Linux only)
	find . -type f -name "*.so" -exec strip {} \; 2>/dev/null || true
```

**Result:** ~15 MB PyArrow deployment (well within Lambda 250MB limit)

---

### 3. Lambda Timeout Strategy

#### Timeout Values by Function

```python
# Stock Data Fetcher
timeout = 900  # 15 minutes
# Reason: yfinance rate limit waits can be 15 minutes
# Calculation: 50 symbols * 2s + 15min buffer = 16.7min (rounded to 15min)

# ASX Symbol Updater  
timeout = 180  # 3 minutes
# Reason: Simple HTTP request + CSV parsing
# Calculation: HTTP (30s) + Parse (30s) + Upload (30s) + buffer = 90s

# EventBridge scheduled frequency
data_fetcher: daily at 2 AM AEST
symbol_updater: weekly on Sunday at 3 AM AEST
```

#### Cost Implications

```python
# Lambda Pricing (ap-southeast-2)
# $0.0000166667 per GB-second

# Stock Data Fetcher (512 MB, 15 min timeout)
# Best case: 3 minutes actual
cost_per_run = 0.512 * 180 * 0.0000166667 = $0.00153

# Worst case: 15 minutes (rate limit hit)
cost_per_run = 0.512 * 900 * 0.0000166667 = $0.00768

# Monthly (daily execution)
monthly_cost = $0.00153 * 30 = $0.046 (best case)
monthly_cost = $0.00768 * 30 = $0.230 (worst case)
```

**Conclusion:** 15-minute timeout adds minimal cost (~$0.18/month extra) but prevents failures.

---

### 4. Error Handling Strategy

#### Rate Limit Errors (429)

```python
def fetch_with_rate_limit_handling(symbol: str) -> pd.DataFrame:
    """yfinance handles 429 internally, but we log it."""
    try:
        logger.info(f"Fetching {symbol}")
        data = yf.download(symbol, period="1d", progress=False)
        
        if data.empty:
            logger.warning(f"No data returned for {symbol}")
            return None
            
        logger.info(f"Successfully fetched {symbol}")
        return data
        
    except Exception as e:
        if "429" in str(e) or "Too Many Requests" in str(e):
            logger.warning(f"Rate limited on {symbol} - yfinance handling internally")
            # yfinance already waited, this shouldn't happen often
            raise  # Let it fail and retry on next scheduled run
        else:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
```

#### Retry Strategy

```python
# Exponential backoff for transient errors (not rate limits)
RETRY_DELAYS = [60, 120, 240, 480, 900]  # seconds

def fetch_with_retry(symbol: str, max_retries: int = 5) -> pd.DataFrame:
    """Retry with exponential backoff for transient errors."""
    for attempt in range(max_retries):
        try:
            return yf.download(symbol, period="1d", timeout=900)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            delay = RETRY_DELAYS[attempt]
            logger.warning(f"Attempt {attempt + 1} failed for {symbol}, "
                         f"retrying in {delay}s: {e}")
            time.sleep(delay)
```

---

### 5. Symbol Batching Strategy

#### Recommended Approach

```python
# config/symbols_batch_1.json
{
  "batch_id": 1,
  "symbols": ["BHP", "CBA", "NAB", ...],  # 30 symbols
  "schedule": "cron(0 2 * * ? *)"  # 2 AM daily
}

# config/symbols_batch_2.json
{
  "batch_id": 2,
  "symbols": ["WBC", "ANZ", "CSL", ...],  # 30 symbols
  "schedule": "cron(5 2 * * ? *)"  # 2:05 AM daily
}

# config/symbols_batch_3.json
{
  "batch_id": 3,
  "symbols": ["WES", "WOW", "FMG", ...],  # 30 symbols
  "schedule": "cron(10 2 * * ? *)"  # 2:10 AM daily
}
```

**Benefits:**
- Each batch completes in ~2 minutes normally
- 5-minute stagger prevents concurrent rate limiting
- If one batch hits rate limit, others continue
- Total time: ~15 minutes for 100 symbols

#### Terraform Configuration

```hcl
# Create multiple EventBridge rules
resource "aws_cloudwatch_event_rule" "stock_fetcher_batch" {
  count               = var.symbol_batch_count
  name                = "stock-data-fetcher-batch-${count.index + 1}"
  description         = "Trigger stock fetcher for batch ${count.index + 1}"
  schedule_expression = "cron(${count.index * 5} 2 * * ? *)"
}
```

---

### 6. Monitoring & Alerts

#### Key Metrics to Track

```python
# CloudWatch Custom Metrics
cloudwatch.put_metric_data(
    Namespace='StockStream',
    MetricData=[
        {
            'MetricName': 'SymbolsFetched',
            'Value': symbols_success_count,
            'Unit': 'Count'
        },
        {
            'MetricName': 'SymbolsFailed',
            'Value': symbols_failed_count,
            'Unit': 'Count'
        },
        {
            'MetricName': 'RateLimitHits',
            'Value': rate_limit_count,
            'Unit': 'Count'
        },
        {
            'MetricName': 'ExecutionDuration',
            'Value': duration_seconds,
            'Unit': 'Seconds'
        }
    ]
)
```

#### Alert Thresholds

```yaml
Alerts:
  - Name: HighFailureRate
    Condition: SymbolsFailed / SymbolsFetched > 0.1  # >10% failure
    Action: SNS notification
  
  - Name: FrequentRateLimits
    Condition: RateLimitHits > 2 per day
    Action: SNS notification + reduce symbol count
  
  - Name: LongExecutionTime
    Condition: ExecutionDuration > 600 seconds  # >10 minutes
    Action: CloudWatch log analysis
  
  - Name: LambdaTimeouts
    Condition: Any timeout errors
    Action: SNS critical alert + increase timeout
```

---

## Quick Reference

### Environment Variables (Production)
```bash
YAHOO_FINANCE_TIMEOUT=900
YAHOO_FINANCE_RATE_LIMIT_DELAY=2
YAHOO_FINANCE_MAX_RETRIES=5
YAHOO_FINANCE_RETRY_DELAY=60
```

### Lambda Configuration (Stock Fetcher)
```python
timeout = 900  # 15 minutes
memory = 512   # MB
runtime = "python3.12"
concurrency = 1  # Don't parallelize
```

### Symbol Limits
- **Per batch:** 30-50 symbols
- **Per day:** Unlimited (with batching)
- **Rate limit safe:** 30 symbols/minute

### Package Size Targets
- **Stock Fetcher:** ~25 MB (optimized)
- **Symbol Updater:** ~15 MB (optimized)
- **Lambda limit:** 250 MB unzipped (plenty of room)

### Estimated Costs (Monthly)
- **Lambda execution:** $0.05 - $0.25
- **S3 storage:** $5 - $10 (1 year data)
- **Data transfer:** < $1
- **CloudWatch:** $1 - $2
- **Total:** ~$10/month

---

## Common Pitfalls & Solutions

### ❌ Pitfall 1: Using 5-minute timeout
**Problem:** yfinance waits 15 minutes on rate limit, Lambda times out  
**Solution:** Use 900-second (15-minute) timeout

### ❌ Pitfall 2: Processing too many symbols
**Problem:** Exceeds timeout even without rate limits  
**Solution:** Batch into groups of 30-50 symbols

### ❌ Pitfall 3: Running multiple Lambdas in parallel
**Problem:** All hit rate limit simultaneously  
**Solution:** Stagger execution by 5 minutes per batch

### ❌ Pitfall 4: Not using PyArrow optimization
**Problem:** Lambda package size 50+ MB  
**Solution:** Strip tests and debug symbols (see Makefile)

### ❌ Pitfall 5: Using fastparquet to "save space"
**Problem:** Doesn't save space (Polars needs PyArrow anyway)  
**Solution:** Just use PyArrow, optimize it

---

## Testing Checklist

Before deploying:
- [ ] Test with 5 symbols (should take ~15 seconds)
- [ ] Test with 30 symbols (should take ~70 seconds)
- [ ] Test with 100 symbols (triggers rate limit warning)
- [ ] Verify 2-second delays between requests
- [ ] Verify Lambda package size < 30 MB
- [ ] Verify CloudWatch metrics appearing
- [ ] Test SNS notifications on errors
- [ ] Verify S3 parquet files readable
- [ ] Test backtest with fetched data
- [ ] Monitor costs in AWS Cost Explorer

---

**Last Updated:** December 25, 2025  
**Next Review:** After first deployment
