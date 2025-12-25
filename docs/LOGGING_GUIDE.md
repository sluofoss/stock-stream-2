# Logging Guide - Using Loguru

## TL;DR - Just Use Loguru Directly!

```python
from loguru import logger

# That's it! Logger is pre-configured by modules/common/logger.py
logger.info("Processing symbol", symbol="BHP", rows=1000)
```

## Why This Approach?

The `modules/common/logger.py` file now **only configures** loguru once at import time. It doesn't provide wrapper functions or classes because:

1. ✅ **Loguru's API is already perfect** - no need to wrap it
2. ✅ **Less code to maintain** - went from 164 lines to 65 lines  
3. ✅ **More idiomatic** - use the library as intended
4. ✅ **Better IDE support** - direct imports get better autocomplete
5. ✅ **Clearer documentation** - point devs to loguru's excellent docs

## Auto-Configuration

When any module imports from `modules.common`, the logger is automatically configured:

- **AWS Lambda**: JSON format with full serialization for CloudWatch
- **Local Development**: Colored, human-readable format

No setup needed in your code!

## Usage Examples

### Basic Logging

```python
from loguru import logger

def fetch_data(symbol: str):
    logger.info("Starting fetch", symbol=symbol)
    
    try:
        data = api.get_data(symbol)
        logger.info("Fetch successful", symbol=symbol, rows=len(data))
        return data
    except Exception as e:
        logger.exception("Fetch failed", symbol=symbol)
        raise
```

### Structured Data with .bind()

```python
from loguru import logger

# Bind context for multiple related logs
fetcher_log = logger.bind(module="stock_fetcher", market="ASX")

fetcher_log.info("Processing batch", batch_id=123)
fetcher_log.info("Fetching symbols", count=20)
fetcher_log.warning("Rate limit approaching", requests_left=5)
```

### Exception Logging (Automatic Tracebacks!)

```python
from loguru import logger

try:
    result = risky_operation()
except ValueError as e:
    logger.exception("Validation error", input=data, expected_type="int")
except Exception as e:
    logger.exception("Unexpected error", context="processing_batch")
    raise
```

### Lazy String Formatting

```python
from loguru import logger

# Efficient - only formats if log level is enabled
symbols = ["BHP", "CBA", "NAB"]
logger.debug("Processing {count} symbols: {symbols}", count=len(symbols), symbols=symbols)

# Also works with f-strings
logger.info(f"Processed {count} symbols")
```

### Lambda Function Example

```python
from loguru import logger

def lambda_handler(event, context):
    """AWS Lambda handler with structured logging."""
    # Logger is auto-configured for CloudWatch JSON format
    
    logger.bind(
        request_id=context.request_id,
        function_name=context.function_name,
    ).info("Lambda invocation started", event=event)
    
    try:
        result = process_event(event)
        logger.info("Lambda completed", result=result)
        return {"statusCode": 200, "body": result}
        
    except Exception as e:
        logger.exception("Lambda error", event=event)
        return {"statusCode": 500, "body": str(e)}
```

### Class-Based Usage

```python
from loguru import logger

class StockDataFetcher:
    def __init__(self, market: str):
        self.market = market
        # Bind market context for all logs from this instance
        self.logger = logger.bind(
            class_name=self.__class__.__name__,
            market=market
        )
    
    def fetch(self, symbol: str):
        self.logger.info("Fetching data", symbol=symbol)
        # ... fetch logic ...
        self.logger.info("Fetch complete", symbol=symbol, rows=1000)
```

## Log Levels

```python
logger.debug("Detailed debugging info")      # Development only
logger.info("General information")            # Normal operations
logger.warning("Warning message")             # Potential issues
logger.error("Error occurred")                # Errors that can be handled
logger.critical("Critical failure")           # System-level failures
logger.exception("Error with traceback")      # Automatically includes stack trace
```

## Configuration (Advanced)

Usually not needed, but if you want to customize:

```python
from modules.common.logger import configure_logger

# Force JSON mode locally (for testing CloudWatch parsing)
configure_logger(level="DEBUG", serialize=True)

# Force human-readable in Lambda (for debugging)
configure_logger(level="INFO", serialize=False)
```

## Environment Variables

- `LOG_LEVEL`: Set log level (default: INFO)
- `AWS_LAMBDA_FUNCTION_NAME`: Auto-detected, triggers JSON format

```bash
# Local development with debug logs
export LOG_LEVEL=DEBUG

# In Lambda environment variables
LOG_LEVEL=INFO
```

## CloudWatch Queries

When logs are in JSON format (Lambda), query them easily:

```sql
-- Find all errors
fields @timestamp, message, extra.symbol, extra.error
| filter level.name = "ERROR"
| sort @timestamp desc

-- Track fetch durations
fields @timestamp, extra.duration_ms
| filter message = "Fetch complete"
| stats avg(extra.duration_ms) by bin(5m)

-- Find specific symbol
fields @timestamp, message, level.name
| filter extra.symbol = "BHP"
```

## Migration from Standard Logging

If you have old code using Python's `logging`:

```python
# Old way
import logging
logger = logging.getLogger(__name__)
logger.info("Message", extra={"key": "value"})

# New way - simpler!
from loguru import logger
logger.info("Message", key="value")
```

## What About modules/common/logger.py?

It still exists but is now minimal:
- ✅ Auto-configures loguru once at import time
- ✅ Detects Lambda vs local environment
- ✅ Provides `configure_logger()` for edge cases
- ❌ No wrapper classes (use loguru directly!)
- ❌ No helper functions (use loguru's `.bind()`)

## Benefits of This Approach

1. **Simpler**: Just `from loguru import logger` everywhere
2. **Fewer dependencies**: No custom wrapper code to maintain
3. **Better docs**: Point developers to loguru's excellent documentation
4. **More features**: Full access to loguru's rich API
5. **Cleaner**: Went from 164 lines of wrapper code to 65 lines of config

## Further Reading

- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Loguru GitHub](https://github.com/Delgan/loguru)
- [Loguru API Reference](https://loguru.readthedocs.io/en/stable/api.html)

## Summary

**Just import logger from loguru and use it naturally!** The configuration is already done for you.

```python
from loguru import logger

logger.info("It's that simple!", happy=True, lines_of_wrapper_code=0)
```
