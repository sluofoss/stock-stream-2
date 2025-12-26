# Design Decisions

## Technology Choices

### 1. Python 3.12+
**Decision:** Use Python 3.12 as the minimum version.

**Rationale:**
- Native support for type hints and pattern matching
- Performance improvements (10-15% faster than 3.11)
- Better error messages for debugging
- AWS Lambda supports Python 3.12

**Alternatives Considered:**
- Python 3.11: Rejected due to missing performance improvements
- Python 3.13: Too new, limited AWS Lambda support

### 2. Polars for Data Processing
**Decision:** Use Polars instead of Pandas.

**Rationale:**
- 5-10x faster than Pandas for typical operations
- Lower memory footprint (important for Lambda)
- Native support for lazy evaluation
- Better type safety
- Native Parquet support without PyArrow dependency issues

**Alternatives Considered:**
- Pandas: Rejected due to performance and memory concerns
- DuckDB: Rejected due to SQL-first approach (less Pythonic)
- Dask: Rejected due to complexity and overhead

### 3. Parquet File Format
**Decision:** Use Apache Parquet for data storage.

**Rationale:**
- Columnar format (efficient for analytics)
- 70-80% smaller than CSV with compression
- Preserves data types (no parsing overhead)
- Native support in Polars, Pandas, Arrow
- S3 Select compatible (future optimization)

**Parquet Library Choice: PyArrow over fastparquet**
- **Actively Maintained:** PyArrow is backed by Apache Arrow project (very active)
- **Required Dependency:** Polars requires PyArrow anyway (no extra dependency)
- **Performance:** 2-5x faster read/write than fastparquet
- **Deployment Size:** ~15-20MB (fastparquet ~8MB, but needs pandas which is 40MB+)
- **Lambda Friendly:** When packaged correctly, PyArrow is smaller overall
- **Ecosystem:** Better integration with AWS services and modern data tools

**Alternatives Considered:**
- fastparquet: Rejected - less active development, slower, Polars doesn't use it
- CSV: Rejected due to size and parsing overhead
- JSON: Rejected due to inefficiency
- Avro: Rejected due to less widespread support

**Note:** Since Polars depends on PyArrow, there's no deployment size savings with fastparquet.

### 4. Serverless Architecture (AWS Lambda)
**Decision:** Use AWS Lambda for data fetching and processing.

**Rationale:**
- No server management
- Pay only for execution time
- Automatic scaling
- Easy integration with EventBridge, S3
- Cost-effective for periodic workloads

**Alternatives Considered:**
- EC2: Rejected due to management overhead and cost
- ECS/Fargate: Rejected due to complexity
- AWS Batch: Rejected due to longer cold starts

### 5. Terraform for Infrastructure
**Decision:** Use Terraform for infrastructure as code.

**Rationale:**
- Declarative syntax
- State management
- Wide AWS resource support
- Better than AWS-specific tools for portability
- Large community and module ecosystem

**Alternatives Considered:**
- CloudFormation: Rejected due to verbosity
- CDK: Rejected due to Python/TS complexity
- Pulumi: Rejected due to smaller ecosystem

### 6. Yahoo Finance for Data
**Decision:** Use yfinance library for stock data.

**Rationale:**
- Free and reliable
- No API key required
- Historical data readily available
- Adjusted prices included
- Active maintenance
- Built-in rate limiting (automatically waits on 429 errors)

**Rate Limiting Strategy:**
- 2-second delay between symbol requests (30 symbols/minute)
- 15-minute Lambda timeout to accommodate rate limit pauses
- yfinance automatically handles 429 responses with 15-minute waits
- Exponential backoff for transient errors (60s, 120s, 240s, 480s, 900s)
- Process symbols sequentially, not in parallel

**Alternatives Considered:**
- Alpha Vantage: Rejected due to strict API limits (5 requests/minute)
- Polygon.io: Rejected due to cost ($200+/month for historical data)
- IEX Cloud: Rejected due to limited ASX coverage and cost
- Direct ASX feed: Rejected due to complexity and cost ($1000s/month)

### 7. uv for Package Management
**Decision:** Use uv instead of pip/poetry.

**Rationale:**
- 10-100x faster than pip
- Proper dependency resolution
- Rust-based (reliable)
- Compatible with pip
- Simpler than Poetry

**Alternatives Considered:**
- pip: Rejected due to slow resolution
- Poetry: Rejected due to complexity
- pipenv: Rejected due to poor performance

## Architectural Decisions

### 1. Daily File Granularity
**Decision:** Store one Parquet file per day with all symbols.

**Rationale:**
- Simplifies data organization
- Easy to identify missing dates
- Efficient for date-range queries
- Manageable file sizes (< 1MB per day for 100 symbols)
- Simplifies lifecycle management

**Alternatives Considered:**
- One file per symbol: Rejected (too many files)
- One file per month: Rejected (harder to update)
- One file total: Rejected (too large, hard to update)

### 2. Separate Lambda Functions
**Decision:** Use separate Lambdas for data fetching and symbol updates.

**Rationale:**
- Single Responsibility Principle
- Different execution frequencies
- Easier to debug and monitor
- Different timeout requirements
- Independent scaling

**Alternatives Considered:**
- Single Lambda: Rejected due to complexity
- Step Functions: Rejected due to unnecessary overhead

### 3. S3 as Data Lake
**Decision:** Use S3 as the primary data storage.

**Rationale:**
- Extremely durable (99.999999999%)
- Cost-effective ($0.023/GB)
- Unlimited scalability
- Native integration with Lambda
- Versioning support

**Alternatives Considered:**
- RDS/Aurora: Rejected due to cost and schema rigidity
- DynamoDB: Rejected due to query limitations
- Redshift: Rejected due to overkill and cost

### 4. Local Backtesting
**Decision:** Run backtesting locally, not in Lambda.

**Rationale:**
- Computationally intensive (may exceed Lambda limits)
- Better debugging experience locally
- Cheaper for iterative development
- No cold start delays
- Can be moved to Lambda later if needed

**Alternatives Considered:**
- Lambda backtesting: May implement later for automation

### 5. Stateful Strategy Pattern
**Decision:** Strategies maintain state between data points.

**Rationale:**
- Realistic modeling of trading behavior
- Supports complex strategies (e.g., pairs trading)
- Portfolio-level decisions
- Position sizing based on current holdings
- Risk management

**Alternatives Considered:**
- Stateless strategies: Rejected due to limitations
- Event-driven architecture: Too complex for MVP

### 6. In-Memory Data Processing
**Decision:** Load all data into memory for backtesting.

**Rationale:**
- Fast access for iterative strategies
- Polars handles large datasets efficiently
- Simplifies code
- Daily data is manageable in memory (not tick data)

**Alternatives Considered:**
- Streaming from S3: Rejected due to latency
- Database queries: Rejected due to overhead

### 7. Configuration via JSON Files
**Decision:** Use JSON for configuration (not YAML or TOML).

**Rationale:**
- Native Python support
- Lambda-friendly (no additional dependencies)
- Easy to parse and validate
- S3-compatible
- Schema validation with JSON Schema

**Alternatives Considered:**
- YAML: Rejected (requires PyYAML dependency)
- TOML: Rejected (less common in Lambda)
- Environment variables: Rejected (not suitable for lists)

## Data Schema Decisions

### 1. Date Type for Dates
**Decision:** Use Date32 (not DateTime) for date columns.

**Rationale:**
- Daily granularity is sufficient
- Smaller storage (4 bytes vs 8 bytes)
- Avoids timezone complications
- Simpler queries and comparisons

### 2. Include Adjusted Close
**Decision:** Store both close and adjusted_close.

**Rationale:**
- Essential for backtesting (dividends, splits)
- Minimal storage overhead
- Commonly needed

### 3. Symbol as String
**Decision:** Store symbol as string (not enum/category).

**Rationale:**
- New symbols added dynamically
- Simpler data pipeline
- Minimal storage overhead with Parquet compression

## Security Decisions

### 1. IAM Role-Based Access
**Decision:** Use IAM roles for Lambda, not access keys.

**Rationale:**
- More secure (temporary credentials)
- AWS best practice
- Automatic rotation
- Audit trail via CloudTrail

### 2. S3 Bucket Encryption
**Decision:** Enable S3 server-side encryption (SSE-S3).

**Rationale:**
- Free encryption at rest
- No performance impact
- Compliance requirement
- AWS best practice

### 3. No Public Access
**Decision:** All S3 buckets private, Lambda in VPC (optional).

**Rationale:**
- Data security
- Prevent accidental exposure
- Compliance requirement

## Performance Optimizations

### 1. Lazy Loading with Polars
**Decision:** Use scan_parquet() for large datasets.

**Rationale:**
- Memory-efficient
- Only load needed data
- Polars optimizer handles query planning

### 2. Parquet Compression
**Decision:** Use Snappy compression for Parquet files.

**Rationale:**
- Fast compression/decompression
- Good compression ratio (70-80%)
- CPU-efficient

**Alternatives Considered:**
- GZIP: Rejected (slower decompression)
- Zstd: Considered for cold storage
- No compression: Rejected (storage cost)

### 3. Batch Processing
**Decision:** Fetch multiple symbols per request when possible.

**Rationale:**
- Reduces API calls
- Faster execution
- Lower Lambda invocation costs

### 4. Lambda Package Optimization
**Decision:** Strip unnecessary files from PyArrow in Lambda packages.

**Rationale:**
- PyArrow includes large test files and examples (~50MB uncompressed)
- Lambda has 250MB unzipped, 50MB zipped deployment limits
- Stripping reduces package size by ~30-40%

**Optimization Steps:**
```bash
# In Lambda package, remove:
rm -rf pyarrow/tests/
rm -rf pyarrow/include/
rm -rf pyarrow/*.pyx
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete
```

**Result:** PyArrow deployment size: ~15MB (vs ~50MB unoptimized)

### 5. Rate Limiting Implementation
**Decision:** Sequential processing with delays, not parallel.

**Rationale:**
- Prevents rate limit errors (429)
- More predictable execution time
- Easier to debug
- Respects API provider limits

**Implementation:**
```python
import time
for symbol in symbols:
    data = yfinance.download(symbol)
    time.sleep(2)  # Rate limit protection
```

## Testing Decisions

### 1. Pytest for Testing
**Decision:** Use pytest as the testing framework.

**Rationale:**
- Industry standard
- Rich plugin ecosystem
- Fixture support
- Parametrized testing
- Better error messages than unittest

### 2. Separate Unit and Integration Tests
**Decision:** Clear separation between unit and integration tests.

**Rationale:**
- Fast unit tests for development
- Integration tests require AWS credentials
- Different CI/CD execution

### 3. Mock AWS Services
**Decision:** Use moto for mocking AWS services in tests.

**Rationale:**
- Fast test execution
- No AWS costs for testing
- Repeatable tests
- No cleanup required

## Monitoring Decisions

### 1. CloudWatch for Logging
**Decision:** Use CloudWatch Logs for Lambda logging.

**Rationale:**
- Native integration
- No additional setup
- Query capabilities
- Retention policies
- Cost-effective

### 2. Structured Logging
**Decision:** Log in JSON format with structured fields.

**Rationale:**
- Easy to parse and query
- Better for log aggregation
- Machine-readable
- CloudWatch Insights compatibility

### 3. Error Notifications
**Decision:** Use SNS for error notifications.

**Rationale:**
- Simple pub/sub model
- Multiple subscribers (email, SMS, Lambda)
- Low cost
- Reliable delivery

## Future Considerations

### 1. Real-Time Data
**Decision:** Not implemented in MVP, but architecture supports it.

**Approach:**
- WebSocket connection for real-time updates
- Separate Lambda for streaming data
- Different S3 prefix for intraday data

### 2. Machine Learning
**Decision:** Not in MVP, but data schema supports it.

**Approach:**
- Export data to SageMaker
- Feature engineering pipeline
- Model training and deployment
- Prediction integration with strategies

### 3. Multi-Region Deployment
**Decision:** Single region for MVP (ap-southeast-2).

**Approach:**
- S3 cross-region replication
- Multi-region Terraform modules
- Regional Lambda deployments
- Global DynamoDB tables for state

### 4. Cost Optimization
**Decision:** Basic cost controls in MVP.

**Future Optimizations:**
- S3 Intelligent-Tiering
- Reserved Lambda concurrency
- CloudWatch log sampling
- Spot instances for batch processing
