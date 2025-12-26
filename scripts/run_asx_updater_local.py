#!/usr/bin/env python3
"""Local testing script for ASX Symbol Updater.

This script runs the ASX Symbol Updater with configurable mock modes for local testing.

Mock Modes:
- MOCK_ASX_SOURCE=true: Use mock ASX data (10 companies) instead of scraping website
- MOCK_AWS=true: Skip S3 uploads/downloads (no AWS credentials needed)

Usage Examples:
    # Full mock mode (no network, no AWS)
    python scripts/run_asx_updater_local.py
    
    # Test real ASX website scraping, mock AWS
    MOCK_ASX_SOURCE=false python scripts/run_asx_updater_local.py
    
    # Test everything with real AWS S3
    MOCK_ASX_SOURCE=false MOCK_AWS=false S3_BUCKET=my-bucket python scripts/run_asx_updater_local.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set environment variables for local testing (can be overridden)
os.environ.setdefault("S3_BUCKET", "stock-stream-test")
os.environ.setdefault("MOCK_AWS", "true")  # Mock AWS S3 operations by default
os.environ.setdefault("MOCK_ASX_SOURCE", "true")  # Mock ASX website by default
os.environ.setdefault("LOG_LEVEL", "INFO")

# Import and run the handler
from modules.asx_symbol_updater.handler import lambda_handler


class MockContext:
    """Mock AWS Lambda context for local testing."""
    request_id = "local-test"
    function_name = "asx-symbol-updater-local"


if __name__ == "__main__":
    # Display configuration
    mock_asx = os.environ.get("MOCK_ASX_SOURCE", "true") == "true"
    mock_aws = os.environ.get("MOCK_AWS", "true") == "true"
    
    print("=" * 80)
    print("ASX Symbol Updater - Local Test Mode")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  - MOCK_ASX_SOURCE: {mock_asx} {'(using 10 mock companies)' if mock_asx else '(scraping real ASX website)'}")
    print(f"  - MOCK_AWS: {mock_aws} {'(skipping S3 operations)' if mock_aws else '(using real S3)'}")
    print(f"  - S3_BUCKET: {os.environ.get('S3_BUCKET')}")
    print()
    
    # Run the handler
    result = lambda_handler({}, MockContext())
    
    print()
    print("=" * 80)
    print("Execution Complete")
    print("=" * 80)
    print()
    print(f"Status Code: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        metadata = result['metadata']
        print(f"✅ SUCCESS")
        print(f"  - Total Symbols: {metadata['total_symbols']}")
        print(f"  - Number of Batches: {metadata['num_batches']}")
        print(f"  - Batch Size: {metadata['batch_size']}")
        print(f"  - S3 Key: {metadata['s3_key']}")
        print(f"  - Execution Time: {metadata['execution_time']:.3f}s")
        print()
        print(f"Symbol Batches:")
        for batch in result['symbolBatches']:
            print(f"  - Batch {batch['batchNumber']}: {len(batch['symbols'])} symbols")
    else:
        print(f"❌ FAILED")
        print(f"  - Error: {result.get('body', 'Unknown error')}")
