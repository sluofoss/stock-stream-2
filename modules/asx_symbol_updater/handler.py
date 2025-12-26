"""AWS Lambda handler for ASX symbol updater."""

import csv
import json
import os
from datetime import date, datetime
from io import StringIO
from typing import Any

import boto3
import requests
from bs4 import BeautifulSoup
from loguru import logger

from modules.common.exceptions import StockStreamError

# Auto-configure logger for Lambda or local environment
from modules.common import logger as _  # noqa: F401 - triggers auto-configuration

# Constants
ASX_DIRECTORY_URL = "https://www.asx.com.au/markets/trade-our-cash-market/directory"
# ASX_CSV_DIRECT_URL = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"  # Direct CSV download, missing listing date and market cap
ASX_CSV_DIRECT_URL = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory/file"
S3_SYMBOLS_PREFIX = "symbols/"
BATCH_SIZE = 100


class ASXSymbolUpdaterError(StockStreamError):
    """Error specific to ASX Symbol Updater."""
    pass


def extract_csv_download_url(html_content: str) -> str:
    """Extract the CSV download URL from the ASX directory page.
    
    Args:
        html_content: HTML content of the ASX directory page
        
    Returns:
        CSV download URL
        
    Raises:
        ASXSymbolUpdaterError: If CSV download link not found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Look for the CSV download link
    # The link text is "All ASX listed companies (CSV download)"
    csv_link = soup.find('a', string=lambda text: text and 'CSV download' in text)
    
    if not csv_link:
        # Try alternate approach - look for data-download attribute or onclick
        csv_link = soup.find('a', {'data-download': True})
    
    if not csv_link:
        raise ASXSymbolUpdaterError(
            "Could not find CSV download link on ASX directory page",
            details={"url": ASX_DIRECTORY_URL}
        )
    
    # Get the actual download URL from onclick or href
    onclick = csv_link.get('onclick', '')
    href = csv_link.get('href', '')
    
    # The onclick might contain a URL
    if 'http' in onclick:
        import re
        urls = re.findall(r'https?://[^\s\'"]+', onclick)
        if urls:
            return urls[0]
    
    if href and href.startswith('http'):
        return href
    elif href and not href.startswith('javascript'):
        # Relative URL
        return f"https://www.asx.com.au{href}"
    
    raise ASXSymbolUpdaterError(
        "Could not extract CSV download URL from link",
        details={"onclick": onclick, "href": href}
    )


def download_asx_csv() -> str:
    """Download ASX listed companies CSV.
    
    Returns:
        CSV content as string
        
    Raises:
        ASXSymbolUpdaterError: If download fails
    """
    # Mock ASX source for local testing (use small mock data)
    if os.getenv("MOCK_ASX_SOURCE") == "true":
        logger.info("Using mock ASX data for local testing")
        mock_csv = """ASX code,Company name,GICS industry group,Market Cap
BHP,BHP Group Limited,Materials,180500000000
CBA,Commonwealth Bank,Financials,165200000000
NAB,National Australia Bank,Financials,98450000000
WBC,Westpac Banking Corporation,Financials,87320000000
ANZ,Australia and New Zealand Banking Group,Financials,75690000000
CSL,CSL Limited,Health Care Equipment & Services,142300000000
WES,Wesfarmers Limited,Consumer Discretionary Distribution & Retail,68900000000
WOW,Woolworths Group,Consumer Staples Distribution & Retail,45200000000
FMG,Fortescue Metals Group,Materials,56800000000
RIO,Rio Tinto Limited,Materials,134700000000"""
        return mock_csv
    
    try:
        logger.info("Fetching ASX directory page", url=ASX_DIRECTORY_URL)
        
        # First, try the direct CSV URL (more reliable)
        try:
            logger.info("Attempting direct CSV download", url=ASX_CSV_DIRECT_URL)
            csv_response = requests.get(
                ASX_CSV_DIRECT_URL,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout=60
            )
            csv_response.raise_for_status()
            
            csv_content = csv_response.text
            logger.info(
                "Successfully downloaded ASX CSV (direct URL)",
                size_bytes=len(csv_content),
                num_lines=csv_content.count('\n')
            )
            
            # Log the full list length (after parsing)
            try:
                companies = parse_asx_csv(csv_content)
                logger.info(
                    f"ASX CSV contains {len(companies)} companies",
                    total_companies=len(companies),
                    sample_symbols=[c['symbol'] for c in companies[:5]]
                )
            except Exception as e:
                logger.warning(f"Could not parse CSV for preview: {str(e)}")
            
            return csv_content
            
        except requests.exceptions.RequestException as direct_error:
            logger.warning(
                f"Direct CSV download failed, trying directory page: {str(direct_error)}",
                url=ASX_CSV_DIRECT_URL
            )
        
        # Fallback: Get the directory page to find the CSV download link
        response = requests.get(
            ASX_DIRECTORY_URL,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=30
        )
        response.raise_for_status()
        
        # Extract CSV download URL
        csv_url = extract_csv_download_url(response.text)
        logger.info("Found CSV download URL", url=csv_url)
        
        # Download the CSV
        csv_response = requests.get(
            csv_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=60
        )
        csv_response.raise_for_status()
        
        csv_content = csv_response.text
        logger.info(
            "Successfully downloaded ASX CSV",
            size_bytes=len(csv_content),
            num_lines=csv_content.count('\n')
        )
        
        # Log the full list length (after parsing)
        try:
            companies = parse_asx_csv(csv_content)
            logger.info(
                f"ASX CSV contains {len(companies)} companies",
                total_companies=len(companies),
                sample_symbols=[c['symbol'] for c in companies[:5]]
            )
        except Exception as e:
            logger.warning(f"Could not parse CSV for preview: {str(e)}")
        
        return csv_content
        
    except requests.exceptions.RequestException as e:
        raise ASXSymbolUpdaterError(
            f"Failed to download ASX CSV: {str(e)}",
            details={"error": str(e), "url": ASX_DIRECTORY_URL}
        )


def parse_asx_csv(csv_content: str) -> list[dict[str, str]]:
    """Parse ASX CSV content into list of company dictionaries.
    
    Args:
        csv_content: CSV content as string
        
    Returns:
        List of dictionaries with keys: symbol, name, sector, market_cap
        
    Raises:
        ASXSymbolUpdaterError: If CSV parsing fails
    """
    try:
        # Skip header lines (ASX CSV often has a header line before the CSV data)
        lines = csv_content.strip().split('\n')
        
        # Find the first line that looks like a CSV header (contains commas and relevant keywords)
        csv_start_idx = 0
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['code', 'symbol', 'company', 'name']):
                csv_start_idx = i
                break
        
        csv_data = '\n'.join(lines[csv_start_idx:])
        reader = csv.DictReader(StringIO(csv_data))
        companies = []
        
        for row in reader:
            # Extract relevant fields
            # CSV columns may vary, so we handle different possible column names
            symbol = (
                row.get('ASX code') or 
                row.get('Code') or 
                row.get('Symbol') or 
                row.get('Ticker') or
                row.get('ASX Code') or
                ''
            ).strip()
            
            name = (
                row.get('Company name') or 
                row.get('Name') or 
                row.get('Company') or
                ''
            ).strip()
            
            sector = (
                row.get('GICS industry group') or 
                row.get('Industry') or 
                row.get('Sector') or
                'Unknown'
            ).strip()
            
            market_cap = (
                row.get('Market Cap') or 
                row.get('MarketCap') or 
                ''
            ).strip()
            
            if symbol and name:
                companies.append({
                    'symbol': symbol,
                    'name': name,
                    'sector': sector,
                    'market_cap': market_cap
                })
        
        if not companies:
            raise ASXSymbolUpdaterError(
                "No companies found in CSV",
                details={"error": "No companies found in CSV", "csv_preview": csv_content[:500]}
            )
        
        logger.info(f"Parsed {len(companies)} companies from CSV")
        return companies
        
    except Exception as e:
        if isinstance(e, ASXSymbolUpdaterError):
            raise
        raise ASXSymbolUpdaterError(
            f"Failed to parse ASX CSV: {str(e)}",
            details={"error": str(e), "csv_preview": csv_content[:500]}
        )


def upload_to_s3(csv_content: str, bucket: str, upload_date: date) -> str:
    """Upload CSV content to S3.
    
    Args:
        csv_content: CSV content as string
        bucket: S3 bucket name
        upload_date: Date for the file
        
    Returns:
        S3 key of uploaded file
        
    Raises:
        ASXSymbolUpdaterError: If upload fails
    """
    s3_key = f"{S3_SYMBOLS_PREFIX}{upload_date.isoformat()}-symbols.csv"
    
    # Mock AWS for local testing (skip S3 upload)
    if os.getenv("MOCK_AWS") == "true":
        logger.info(
            f"Mock AWS: Would upload to S3",
            bucket=bucket,
            key=s3_key,
            size_bytes=len(csv_content)
        )
        return s3_key
    
    s3_client = boto3.client('s3')
    
    try:
        logger.info(
            f"Uploading to S3",
            bucket=bucket,
            key=s3_key,
            size_bytes=len(csv_content)
        )
        
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv',
            Metadata={
                'source': 'asx-website',
                'upload_date': upload_date.isoformat(),
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )
        
        logger.info("Successfully uploaded to S3", key=s3_key)
        return s3_key
        
    except Exception as e:
        raise ASXSymbolUpdaterError(
            f"Failed to upload to S3: {str(e)}",
            details={"bucket": bucket, "key": s3_key, "error": str(e)}
        )


def get_latest_symbols_from_s3(bucket: str) -> list[dict[str, str]]:
    """Get the latest symbols CSV from S3.
    
    Args:
        bucket: S3 bucket name
        
    Returns:
        List of company dictionaries
        
    Raises:
        ASXSymbolUpdaterError: If retrieval fails
    """
    # Mock AWS for local testing - return mock data
    if os.getenv("MOCK_AWS") == "true":
        logger.info("Mock AWS: Using mock symbols data for S3 retrieval")
        mock_csv = """ASX code,Company name,GICS industry group,Market Cap
BHP,BHP Group Limited,Materials,180500000000
CBA,Commonwealth Bank,Financials,165200000000
NAB,National Australia Bank,Financials,98450000000
WBC,Westpac Banking Corporation,Financials,87320000000
ANZ,Australia and New Zealand Banking Group,Financials,75690000000
CSL,CSL Limited,Health Care Equipment & Services,142300000000
WES,Wesfarmers Limited,Consumer Discretionary Distribution & Retail,68900000000
WOW,Woolworths Group,Consumer Staples Distribution & Retail,45200000000
FMG,Fortescue Metals Group,Materials,56800000000
RIO,Rio Tinto Limited,Materials,134700000000"""
        return parse_asx_csv(mock_csv)
    
    s3_client = boto3.client('s3')
    
    try:
        # List all files in the symbols prefix
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=S3_SYMBOLS_PREFIX
        )
        
        if 'Contents' not in response:
            raise ASXSymbolUpdaterError(
                "No symbol files found in S3",
                details={"bucket": bucket, "prefix": S3_SYMBOLS_PREFIX}
            )
        
        # Sort by last modified date to get the latest
        files = sorted(
            response['Contents'],
            key=lambda x: x['LastModified'],
            reverse=True
        )
        
        latest_key = files[0]['Key']
        logger.info(f"Latest symbols file: {latest_key}")
        
        # Download the file
        obj = s3_client.get_object(Bucket=bucket, Key=latest_key)
        csv_content = obj['Body'].read().decode('utf-8')
        
        # Parse and return
        return parse_asx_csv(csv_content)
        
    except Exception as e:
        raise ASXSymbolUpdaterError(
            f"Failed to get latest symbols from S3: {str(e)}",
            details={"bucket": bucket, "prefix": S3_SYMBOLS_PREFIX, "error": str(e)}
        )


def split_into_batches(symbols: list[str], batch_size: int = BATCH_SIZE) -> list[dict[str, Any]]:
    """Split symbols into batches for Step Functions Map state.
    
    Args:
        symbols: List of stock symbols
        batch_size: Number of symbols per batch
        
    Returns:
        List of batch dictionaries for Step Functions
    """
    batches = []
    
    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i:i + batch_size]
        batches.append({
            "symbols": batch_symbols,
            "batchNumber": i // batch_size
        })
    
    logger.info(
        f"Split {len(symbols)} symbols into {len(batches)} batches",
        total_symbols=len(symbols),
        num_batches=len(batches),
        batch_size=batch_size
    )
    
    return batches


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for ASX symbol updater.
    
    This handler:
    1. Downloads the latest ASX companies CSV from the ASX website
    2. Uploads it to S3 with today's date
    3. Retrieves the latest file from S3 (the one just uploaded)
    4. Splits symbols into batches of 100
    5. Returns formatted output for Step Functions
    
    Args:
        event: EventBridge/Step Functions event
        context: AWS Lambda context object
        
    Returns:
        Dictionary with symbols and batches for Step Functions
    """
    start_time = datetime.utcnow()
    request_id = context.request_id if hasattr(context, "request_id") else "local"
    
    logger.info(
        "ASX Symbol Updater started",
        request_id=request_id,
        event=event
    )
    
    try:
        # Get configuration from environment
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise ASXSymbolUpdaterError("S3_BUCKET environment variable not set")
        
        upload_date = date.today()
        
        # Step 1: Download CSV from ASX website
        logger.info("Step 1: Downloading ASX CSV from website")
        csv_content = download_asx_csv()
        
        # Parse to validate
        companies = parse_asx_csv(csv_content)
        logger.info(f"Downloaded and parsed {len(companies)} companies")
        
        # Step 2: Upload to S3
        logger.info("Step 2: Uploading CSV to S3")
        s3_key = upload_to_s3(csv_content, bucket, upload_date)
        
        # Step 3: Get the latest file from S3 (the one we just uploaded)
        # If MOCK_AWS=true, we need to use the real data we downloaded, not mock data
        logger.info("Step 3: Retrieving latest symbols from S3")
        if os.getenv("MOCK_AWS") == "true":
            # In mock AWS mode, use the CSV we just downloaded instead of fetching from S3
            logger.info("Mock AWS: Using downloaded CSV data instead of S3 retrieval")
            latest_companies = companies  # Use the companies we already parsed
        else:
            # Real AWS mode: fetch from S3
            latest_companies = get_latest_symbols_from_s3(bucket)
        
        # Extract just the symbols for processing
        symbols = [company['symbol'] for company in latest_companies]
        
        # Step 4: Split into batches for Step Functions
        logger.info("Step 4: Splitting symbols into batches")
        symbol_batches = split_into_batches(symbols, BATCH_SIZE)
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Prepare response for Step Functions
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "message": "ASX symbols updated successfully",
                "date": str(upload_date),
                "total_symbols": len(symbols),
                "num_batches": len(symbol_batches),
                "s3_key": s3_key,
                "execution_time": execution_time
            }),
            "symbols": symbols,  # Flat list for reference
            "symbolBatches": symbol_batches,  # For Step Functions Map state
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "total_symbols": len(symbols),
                "num_batches": len(symbol_batches),
                "batch_size": BATCH_SIZE,
                "s3_key": s3_key,
                "execution_time": execution_time
            }
        }
        
        logger.info(
            "ASX Symbol Updater completed successfully",
            request_id=request_id,
            execution_time=execution_time,
            total_symbols=len(symbols),
            num_batches=len(symbol_batches)
        )
        
        return response
        
    except ASXSymbolUpdaterError as e:
        logger.error(
            f"ASX Symbol Updater error: {e.message}",
            request_id=request_id,
            error_type=type(e).__name__,
            details=e.details
        )
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": type(e).__name__,
                "message": e.message,
                "details": e.details
            }),
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": type(e).__name__
            }
        }
        
    except Exception as e:
        logger.critical(
            f"Unexpected error: {str(e)}",
            request_id=request_id,
            error=str(e)
        )
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "InternalError",
                "message": str(e)
            }),
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": "InternalError"
            }
        }


# For local testing
if __name__ == "__main__":
    # Mock context for local testing
    class MockContext:
        request_id = "local-test"
        function_name = "asx-symbol-updater-local"
    
    # Set environment variable for local testing
    os.environ["S3_BUCKET"] = "stock-stream-test"
    os.environ["MOCK_AWS"] = "true"  # Mock AWS S3 operations
    os.environ["MOCK_ASX_SOURCE"] = "true"  # Mock ASX website data
    
    # Test event
    test_event = {}
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
