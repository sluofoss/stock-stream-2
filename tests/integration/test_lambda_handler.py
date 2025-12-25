"""Integration tests for stock data fetcher Lambda."""

import json
from datetime import date
from unittest.mock import patch

import polars as pl
import pytest
from moto import mock_aws

from modules.stock_data_fetcher.handler import lambda_handler


@mock_aws
class TestLambdaHandler:
    """Integration tests for Lambda handler."""

    @pytest.fixture(autouse=True)
    def setup_aws(self):
        """Set up AWS mocks."""
        import boto3

        # Create S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-stock-data")
        
        # Upload mock config
        config = {"symbols": ["BHP", "CBA", "NAB"]}
        s3.put_object(
            Bucket="test-stock-data",
            Key="config/symbols.json",
            Body=json.dumps(config).encode("utf-8"),
        )

    @patch.dict(
        "os.environ",
        {
            "S3_BUCKET": "test-stock-data",
            "SYMBOLS_CONFIG_KEY": "config/symbols.json",
            "YAHOO_FINANCE_TIMEOUT": "60",
            "RATE_LIMIT_DELAY": "0.1",
            "MAX_RETRIES": "2",
        },
    )
    @patch("yfinance.Ticker")
    def test_lambda_handler_success(self, mock_ticker_class):
        """Test successful Lambda execution."""
        # Setup mock ticker
        mock_df = pl.DataFrame(
            {
                "Date": [date(2024, 12, 25)],
                "Open": [50.0],
                "High": [52.0],
                "Low": [49.0],
                "Close": [51.0],
                "Volume": [1000000],
                "Adj Close": [51.0],
            }
        ).to_pandas()
        
        from unittest.mock import MagicMock
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        mock_ticker_class.return_value = mock_ticker

        # Create event
        event = {
            "start_date": "2024-12-25",
            "end_date": "2024-12-26",
        }

        # Execute
        response = lambda_handler(event, None)

        # Verify
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["symbols_processed"] == 3

    @patch.dict(
        "os.environ",
        {
            "S3_BUCKET": "test-stock-data",
            "SYMBOLS_CONFIG_KEY": "config/symbols.json",
            "YAHOO_FINANCE_TIMEOUT": "60",
            "RATE_LIMIT_DELAY": "0.1",
            "MAX_RETRIES": "2",
        },
    )
    def test_lambda_handler_missing_dates(self):
        """Test Lambda with missing date parameters."""
        event = {}  # No dates provided
        response = lambda_handler(event, None)

        # Should use default dates (today)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "start_date" in body
        assert "end_date" in body

    @patch.dict("os.environ", {"S3_BUCKET": "test-stock-data"})
    def test_lambda_handler_invalid_config(self):
        """Test Lambda with invalid configuration."""
        import boto3

        # Remove config file
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.delete_object(Bucket="test-stock-data", Key="config/symbols.json")

        event = {"start_date": "2024-12-25", "end_date": "2024-12-26"}
        response = lambda_handler(event, None)

        # Should return error
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["status"] == "error"

    @patch.dict(
        "os.environ",
        {
            "S3_BUCKET": "test-stock-data",
            "SYMBOLS_CONFIG_KEY": "config/symbols.json",
            "YAHOO_FINANCE_TIMEOUT": "60",
            "RATE_LIMIT_DELAY": "0.1",
            "MAX_RETRIES": "1",
        },
    )
    @patch("yfinance.Ticker")
    def test_lambda_handler_partial_failure(self, mock_ticker_class):
        """Test Lambda with some symbol failures."""
        from unittest.mock import MagicMock
        
        # Setup mock to fail for first symbol, succeed for others
        mock_ticker = MagicMock()
        call_count = 0
        
        def history_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return pl.DataFrame(
                {
                    "Date": [date(2024, 12, 25)],
                    "Open": [50.0],
                    "High": [52.0],
                    "Low": [49.0],
                    "Close": [51.0],
                    "Volume": [1000000],
                    "Adj Close": [51.0],
                }
            ).to_pandas()
        
        mock_ticker.history.side_effect = history_side_effect
        mock_ticker_class.return_value = mock_ticker

        event = {"start_date": "2024-12-25", "end_date": "2024-12-26"}
        response = lambda_handler(event, None)

        # Should still succeed but with errors reported
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["symbols_processed"] < 3
        assert "errors" in body
