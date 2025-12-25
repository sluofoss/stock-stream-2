"""Unit tests for the S3Storage class."""

from datetime import date
from unittest.mock import MagicMock, Mock, patch

import polars as pl
import pytest
from botocore.exceptions import ClientError

from modules.common.exceptions import StorageError
from modules.stock_data_fetcher.storage import S3Storage


class TestS3Storage:
    """Tests for S3Storage class."""

    @pytest.fixture
    def storage(self) -> S3Storage:
        """Create an S3Storage instance for testing."""
        return S3Storage(bucket_name="test-bucket")

    @pytest.fixture
    def sample_dataframe(self) -> pl.DataFrame:
        """Create a sample DataFrame for testing."""
        return pl.DataFrame(
            {
                "symbol": ["BHP", "BHP", "BHP"],
                "date": [date(2024, 12, 24), date(2024, 12, 25), date(2024, 12, 26)],
                "open": [50.0, 51.0, 52.0],
                "high": [52.0, 53.0, 54.0],
                "low": [49.0, 50.0, 51.0],
                "close": [51.0, 52.0, 53.0],
                "volume": [1000000, 1100000, 1200000],
                "adjusted_close": [51.0, 52.0, 53.0],
            }
        )

    def test_initialization(self, storage: S3Storage) -> None:
        """Test storage initialization."""
        assert storage.bucket_name == "test-bucket"
        assert storage.s3_client is not None

    @patch("boto3.client")
    def test_upload_dataframe_success(
        self, mock_boto_client: Mock, storage: S3Storage, sample_dataframe: pl.DataFrame
    ) -> None:
        """Test successful DataFrame upload."""
        # Setup mock
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        s3_key = "raw/BHP/2024-12-25.parquet"
        result = storage.upload_dataframe(sample_dataframe, s3_key)

        # Verify
        assert result is True
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == s3_key
        assert call_kwargs["ContentType"] == "application/x-parquet"

    @patch("boto3.client")
    def test_upload_dataframe_failure(
        self, mock_boto_client: Mock, storage: S3Storage, sample_dataframe: pl.DataFrame
    ) -> None:
        """Test DataFrame upload failure."""
        # Setup mock to raise error
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        s3_key = "raw/BHP/2024-12-25.parquet"
        with pytest.raises(StorageError):
            storage.upload_dataframe(sample_dataframe, s3_key)

    @patch("boto3.client")
    def test_upload_local_file_success(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test successful local file upload."""
        # Setup mock
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        local_path = "/tmp/test.parquet"
        s3_key = "raw/test.parquet"
        result = storage.upload_local_file(local_path, s3_key)

        # Verify
        assert result is True
        mock_s3.upload_file.assert_called_once_with(local_path, "test-bucket", s3_key)

    @patch("boto3.client")
    def test_download_dataframe_success(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test successful DataFrame download."""
        # Setup mock
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Mock the get_object response with Parquet data
        mock_body = MagicMock()
        mock_body.read.return_value = b"fake_parquet_data"
        mock_s3.get_object.return_value = {"Body": mock_body}

        # Mock polars read_parquet to return a DataFrame
        with patch("polars.read_parquet") as mock_read_parquet:
            mock_df = pl.DataFrame({"col": [1, 2, 3]})
            mock_read_parquet.return_value = mock_df

            # Test
            s3_key = "raw/BHP/2024-12-25.parquet"
            result = storage.download_dataframe(s3_key)

            # Verify
            assert isinstance(result, pl.DataFrame)
            mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key=s3_key)

    @patch("boto3.client")
    def test_download_dataframe_not_found(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test DataFrame download when file doesn't exist."""
        # Setup mock to raise NoSuchKey error
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}}, "GetObject"
        )
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        s3_key = "raw/BHP/2024-12-25.parquet"
        with pytest.raises(StorageError, match="does not exist"):
            storage.download_dataframe(s3_key)

    @patch("boto3.client")
    def test_file_exists_true(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test checking if file exists (returns True)."""
        # Setup mock
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1024}
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        s3_key = "raw/BHP/2024-12-25.parquet"
        result = storage.file_exists(s3_key)

        # Verify
        assert result is True
        mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key=s3_key)

    @patch("boto3.client")
    def test_file_exists_false(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test checking if file exists (returns False)."""
        # Setup mock to raise NoSuchKey error
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "HeadObject"
        )
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        s3_key = "raw/BHP/2024-12-25.parquet"
        result = storage.file_exists(s3_key)

        # Verify
        assert result is False

    @patch("boto3.client")
    def test_list_files(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test listing files with a prefix."""
        # Setup mock
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "raw/BHP/2024-12-25.parquet"},
                {"Key": "raw/BHP/2024-12-26.parquet"},
            ]
        }
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        prefix = "raw/BHP/"
        result = storage.list_files(prefix)

        # Verify
        assert len(result) == 2
        assert "raw/BHP/2024-12-25.parquet" in result
        assert "raw/BHP/2024-12-26.parquet" in result
        mock_s3.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix=prefix)

    @patch("boto3.client")
    def test_list_files_empty(self, mock_boto_client: Mock, storage: S3Storage) -> None:
        """Test listing files when none exist."""
        # Setup mock with no contents
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {}
        mock_boto_client.return_value = mock_s3
        storage.s3_client = mock_s3

        # Test
        prefix = "raw/NONEXISTENT/"
        result = storage.list_files(prefix)

        # Verify
        assert len(result) == 0
