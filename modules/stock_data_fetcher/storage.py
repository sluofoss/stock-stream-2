"""S3 storage utilities for stock data."""

from datetime import date
from pathlib import Path

import boto3
import polars as pl

from modules.common.exceptions import StorageError
from modules.common.logger import get_logger

logger = get_logger(__name__)


class S3Storage:
    """Handles storage of stock data to S3 in Parquet format."""

    def __init__(self, bucket: str, prefix: str = "raw-data/", region: str = "ap-southeast-2") -> None:
        """Initialize S3 storage.

        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix for data files
            region: AWS region
        """
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        self.region = region
        self.s3_client = boto3.client("s3", region_name=region)

    def upload_dataframe(
        self, df: pl.DataFrame, upload_date: date | None = None, batch_number: int | None = None
    ) -> str:
        """Upload DataFrame to S3 as Parquet file.

        Args:
            df: Polars DataFrame with stock data
            upload_date: Date for the file (defaults to today)
            batch_number: Optional batch number for parallel processing (e.g., 0, 1, 2...)

        Returns:
            S3 key of uploaded file (e.g., "raw-data/2025-12-26-batch-0.parquet")

        Raises:
            StorageError: If upload fails
        """
        if df.height == 0:
            raise StorageError("Cannot upload empty DataFrame")

        # Use provided date or today's date
        file_date = upload_date or date.today()
        
        # Create filename with optional batch number
        if batch_number is not None:
            filename = f"{file_date.isoformat()}-batch-{batch_number}.parquet"
        else:
            filename = f"{file_date.isoformat()}.parquet"
        
        s3_key = f"{self.prefix}{filename}"

        try:
            # Write DataFrame to Parquet in memory
            logger.info(
                f"Writing {df.height} rows to Parquet format",
                rows=df.height,
                date=str(file_date),
                batch_number=batch_number,
            )

            # Write to temporary file first
            temp_path = f"/tmp/{filename}"
            df.write_parquet(temp_path, compression="snappy")

            # Upload to S3
            logger.info(
                f"Uploading to s3://{self.bucket}/{s3_key}",
                bucket=self.bucket,
                key=s3_key,
            )

            self.s3_client.upload_file(temp_path, self.bucket, s3_key)

            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

            logger.info(
                f"Successfully uploaded to S3",
                bucket=self.bucket,
                key=s3_key,
                rows=df.height,
            )

            return s3_key

        except Exception as e:
            raise StorageError(
                f"Failed to upload data to S3: {str(e)}",
                details={
                    "bucket": self.bucket,
                    "key": s3_key,
                    "rows": df.height,
                    "error": str(e),
                },
            )

    def upload_local_file(self, file_path: str, s3_key: str) -> None:
        """Upload a local Parquet file to S3.

        Args:
            file_path: Path to local Parquet file
            s3_key: S3 key for upload

        Raises:
            StorageError: If upload fails
        """
        try:
            logger.info(
                f"Uploading {file_path} to s3://{self.bucket}/{s3_key}",
                file_path=file_path,
                bucket=self.bucket,
                key=s3_key,
            )

            self.s3_client.upload_file(file_path, self.bucket, s3_key)

            logger.info(f"Successfully uploaded {file_path} to S3", file_path=file_path)

        except Exception as e:
            raise StorageError(
                f"Failed to upload file to S3: {str(e)}",
                details={
                    "file_path": file_path,
                    "bucket": self.bucket,
                    "key": s3_key,
                    "error": str(e),
                },
            )

    def file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3.

        Args:
            s3_key: S3 key to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def download_dataframe(self, s3_key: str) -> pl.DataFrame:
        """Download Parquet file from S3 and return as DataFrame.

        Args:
            s3_key: S3 key of Parquet file

        Returns:
            Polars DataFrame

        Raises:
            StorageError: If download fails
        """
        try:
            logger.info(
                f"Downloading s3://{self.bucket}/{s3_key}",
                bucket=self.bucket,
                key=s3_key,
            )

            # Download to temporary file
            temp_path = f"/tmp/download_{Path(s3_key).name}"
            self.s3_client.download_file(self.bucket, s3_key, temp_path)

            # Read Parquet file
            df = pl.read_parquet(temp_path)

            # Clean up
            Path(temp_path).unlink(missing_ok=True)

            logger.info(
                f"Successfully downloaded {df.height} rows",
                rows=df.height,
                key=s3_key,
            )

            return df

        except Exception as e:
            raise StorageError(
                f"Failed to download from S3: {str(e)}",
                details={"bucket": self.bucket, "key": s3_key, "error": str(e)},
            )
