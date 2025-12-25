"""Configuration management for stock data fetcher."""

import json
import os
from typing import Any

import boto3

from modules.common.exceptions import ConfigurationError
from modules.common.logger import get_logger
from modules.common.validators import validate_config

logger = get_logger(__name__)


class Config:
    """Configuration manager for stock data fetcher."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.s3_bucket = os.getenv("S3_BUCKET_NAME", "")
        self.s3_raw_data_prefix = os.getenv("S3_RAW_DATA_PREFIX", "raw-data/")
        self.s3_config_prefix = os.getenv("S3_CONFIG_PREFIX", "config/")
        self.yahoo_timeout = int(os.getenv("YAHOO_FINANCE_TIMEOUT", "900"))
        self.yahoo_max_retries = int(os.getenv("YAHOO_FINANCE_MAX_RETRIES", "5"))
        self.yahoo_retry_delay = int(os.getenv("YAHOO_FINANCE_RETRY_DELAY", "60"))
        self.yahoo_rate_limit_delay = float(
            os.getenv("YAHOO_FINANCE_RATE_LIMIT_DELAY", "2")
        )
        self.aws_region = os.getenv("AWS_REGION", "ap-southeast-2")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        if not self.s3_bucket:
            raise ConfigurationError("S3_BUCKET_NAME environment variable is required")

    def load_symbols_from_s3(self) -> list[str]:
        """Load symbol list from S3 configuration.

        Returns:
            List of stock symbols

        Raises:
            ConfigurationError: If symbols cannot be loaded
        """
        try:
            s3_client = boto3.client("s3", region_name=self.aws_region)
            key = f"{self.s3_config_prefix}symbols.json"

            logger.info(f"Loading symbols from s3://{self.s3_bucket}/{key}")

            response = s3_client.get_object(Bucket=self.s3_bucket, Key=key)
            config_data = json.loads(response["Body"].read().decode("utf-8"))

            validate_config(config_data)

            symbols = config_data["symbols"]
            logger.info(f"Loaded {len(symbols)} symbols from S3")

            return symbols

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load symbols from S3: {str(e)}",
                details={"bucket": self.s3_bucket, "key": key},
            )

    def load_symbols_from_local(self, path: str = "config/symbols.json") -> list[str]:
        """Load symbol list from local file.

        Args:
            path: Path to symbols.json file

        Returns:
            List of stock symbols

        Raises:
            ConfigurationError: If symbols cannot be loaded
        """
        try:
            with open(path, "r") as f:
                config_data = json.load(f)

            validate_config(config_data)

            symbols = config_data["symbols"]
            logger.info(f"Loaded {len(symbols)} symbols from {path}")

            return symbols

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load symbols from {path}: {str(e)}",
                details={"path": path},
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        return {
            "s3_bucket": self.s3_bucket,
            "s3_raw_data_prefix": self.s3_raw_data_prefix,
            "s3_config_prefix": self.s3_config_prefix,
            "yahoo_timeout": self.yahoo_timeout,
            "yahoo_max_retries": self.yahoo_max_retries,
            "yahoo_retry_delay": self.yahoo_retry_delay,
            "yahoo_rate_limit_delay": self.yahoo_rate_limit_delay,
            "aws_region": self.aws_region,
            "log_level": self.log_level,
        }
