"""AWS Lambda handler for stock data fetcher."""

import json
import os
from datetime import date, datetime
from typing import Any

from modules.common.exceptions import StockStreamError
from modules.common.logger import get_logger
from modules.stock_data_fetcher.config import Config
from modules.stock_data_fetcher.fetcher import YahooFinanceFetcher
from modules.stock_data_fetcher.storage import S3Storage

# Initialize logger
logger = get_logger(__name__, level=os.getenv("LOG_LEVEL", "INFO"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for fetching stock data.

    Invoked by AWS Step Functions as part of a parallel batch processing workflow.
    Each invocation processes up to 100 symbols and saves results to S3 as a separate Parquet file.

    Args:
        event: Step Functions event with the following structure:
            {
                "symbols": List[str],      # Up to 100 symbols to fetch
                "batchNumber": int,        # Batch identifier (0, 1, 2, ...)
                "date": str (optional)     # ISO date format (YYYY-MM-DD)
            }
        context: AWS Lambda context object

    Returns:
        Dictionary with status code, body, and metadata:
        {
            "statusCode": 200,
            "body": JSON string,
            "metadata": {
                "batch_number": int,
                "symbols_processed": int,
                "symbols_fetched": int,
                "symbols_failed": int,
                "execution_time": float,
                "s3_key": str  # e.g., "raw-data/2025-12-26-batch-0.parquet"
            }
        }
    """
    start_time = datetime.utcnow()
    request_id = context.request_id if hasattr(context, "request_id") else "local"
    batch_number = event.get("batchNumber", 0)

    logger.info(
        "Lambda execution started",
        request_id=request_id,
        batch_number=batch_number,
        event=event,
    )

    try:
        # Load configuration
        config = Config()
        logger.info("Configuration loaded", config=config.to_dict())

        # Get symbols from Step Functions event (batch of up to 100)
        if "symbols" in event:
            # Symbols provided by Step Functions
            symbols = event["symbols"]
            logger.info(
                f"Processing batch {batch_number} with {len(symbols)} symbols",
                batch_number=batch_number,
                symbol_count=len(symbols)
            )
        else:
            # Fallback: Load from S3 configuration (for backward compatibility)
            logger.warning("No symbols in event, falling back to S3 configuration")
            try:
                symbols = config.load_symbols_from_s3()
            except Exception as e:
                logger.warning(
                    f"Failed to load symbols from S3: {e}, trying local file"
                )
                symbols = config.load_symbols_from_local()

        # Get fetch date
        fetch_date_str = event.get("date")
        if fetch_date_str:
            fetch_date = datetime.fromisoformat(fetch_date_str).date()
            logger.info(f"Using custom date: {fetch_date}")
        else:
            fetch_date = date.today()
            logger.info(f"Using today's date: {fetch_date}")

        # Initialize fetcher
        fetcher = YahooFinanceFetcher(
            rate_limit_delay=config.yahoo_rate_limit_delay,
            max_retries=config.yahoo_max_retries,
            retry_delay=config.yahoo_retry_delay,
            timeout=config.yahoo_timeout,
        )

        # Fetch data
        logger.info(
            f"Fetching data for batch {batch_number}: {len(symbols)} symbols",
            batch_number=batch_number,
            symbol_count=len(symbols)
        )
        df = fetcher.fetch_multiple_symbols(symbols, fetch_date)

        # Initialize storage
        storage = S3Storage(
            bucket=config.s3_bucket,
            prefix=config.s3_raw_data_prefix,
            region=config.aws_region,
        )

        # Upload to S3 with batch number in filename
        s3_key = storage.upload_dataframe(df, fetch_date, batch_number=batch_number)

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        # Prepare response
        stats = fetcher.get_stats()
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Stock data fetched successfully",
                "date": str(fetch_date),
                "batch_number": batch_number,
                "symbols_processed": stats["total_symbols"],
                "symbols_fetched": stats["symbols_fetched"],
                "symbols_failed": stats["symbols_failed"],
                "s3_key": s3_key,
                "execution_time": execution_time,
            }),
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "batch_number": batch_number,
                "symbols_processed": stats["total_symbols"],
                "symbols_fetched": stats["symbols_fetched"],
                "symbols_failed": stats["symbols_failed"],
                "execution_time": execution_time,
                "s3_key": s3_key,
            },
        }

        logger.info(
            "Lambda execution completed successfully",
            request_id=request_id,
            batch_number=batch_number,
            execution_time=execution_time,
            symbols_fetched=stats["symbols_fetched"],
            symbols_failed=stats["symbols_failed"],
        )

        return response

    except StockStreamError as e:
        logger.error(
            f"Stock stream error: {e.message}",
            request_id=request_id,
            error_type=type(e).__name__,
            details=e.details,
        )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": type(e).__name__,
                "message": e.message,
                "details": e.details,
            }),
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": type(e).__name__,
            },
        }

    except Exception as e:
        logger.critical(
            f"Unexpected error: {str(e)}",
            request_id=request_id,
            error=str(e),
        )

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "InternalError",
                "message": str(e),
            }),
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": "InternalError",
            },
        }


# For local testing
if __name__ == "__main__":
    # Mock context for local testing
    class MockContext:
        request_id = "local-test"
        function_name = "stock-data-fetcher-local"

    # Test event
    test_event = {
        "symbols": ["BHP", "CBA", "NAB"],
        # "date": "2024-12-25"  # Optional: specific date
    }

    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
