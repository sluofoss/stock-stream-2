#!/usr/bin/env python3
"""Test ASX Symbol Updater with real ASX website scraping.

This script downloads the actual ASX company list from the ASX website
and displays the full list of companies. S3 operations are mocked (no AWS needed).

Usage:
    python scripts/run_asx_updater_real_scrape.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure: Real ASX scraping, Mock AWS
os.environ["S3_BUCKET"] = "stock-stream-test"
os.environ["MOCK_AWS"] = "true"  # Skip S3 operations
os.environ["MOCK_ASX_SOURCE"] = "false"  # Use real ASX website
os.environ["LOG_LEVEL"] = "INFO"

# Import and run the handler
from modules.asx_symbol_updater.handler import lambda_handler


class MockContext:
    """Mock AWS Lambda context for local testing."""
    request_id = "real-scrape-test"
    function_name = "asx-symbol-updater-real-scrape"


if __name__ == "__main__":
    print("=" * 80)
    print("ASX Symbol Updater - Real Website Scraping Test")
    print("=" * 80)
    print()
    print("Configuration:")
    print("  - MOCK_ASX_SOURCE: false (downloading from real ASX website)")
    print("  - MOCK_AWS: true (skipping S3 operations)")
    print()
    print("This will take a few seconds to download from the ASX website...")
    print()
    
    # Run the handler
    try:
        result = lambda_handler({}, MockContext())
        
        print()
        print("=" * 80)
        print("Execution Complete")
        print("=" * 80)
        print()
        print(f"Status Code: {result['statusCode']}")
        
        if result['statusCode'] == 200:
            metadata = result['metadata']
            symbols = result['symbols']
            
            print(f"✅ SUCCESS")
            print(f"  - Total Symbols: {metadata['total_symbols']}")
            print(f"  - Number of Batches: {metadata['num_batches']}")
            print(f"  - Batch Size: {metadata['batch_size']}")
            print(f"  - S3 Key: {metadata['s3_key']}")
            print(f"  - Execution Time: {metadata['execution_time']:.3f}s")
            print()
            
            # Display first 20 symbols as preview
            print(f"First 20 Symbols (out of {len(symbols)}):")
            for i, symbol in enumerate(symbols[:20], 1):
                print(f"  {i:2d}. {symbol}")
            
            if len(symbols) > 20:
                print(f"  ... and {len(symbols) - 20} more")
            
            print()
            print(f"Symbol Batches:")
            for batch in result['symbolBatches']:
                batch_num = batch['batchNumber']
                batch_size = len(batch['symbols'])
                first_symbol = batch['symbols'][0]
                last_symbol = batch['symbols'][-1]
                print(f"  - Batch {batch_num}: {batch_size} symbols ({first_symbol} ... {last_symbol})")
        else:
            print(f"❌ FAILED")
            import json
            body = json.loads(result.get('body', '{}'))
            print(f"  - Error: {body.get('message', 'Unknown error')}")
            if 'details' in body:
                print(f"  - Details: {body['details']}")
    
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ EXCEPTION OCCURRED")
        print("=" * 80)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
