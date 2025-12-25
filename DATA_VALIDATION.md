# Data Validation & Quality Rules

## Input Data Validation

### Stock Symbol Validation

#### Format Rules
- **Pattern**: `^[A-Z0-9]{1,5}$`
- **Examples**: Valid: `BHP`, `CBA`, `NAB2`; Invalid: `bhp`, `TOOLONG`, `AB-C`
- **Handling**: Reject invalid symbols with clear error message

#### Existence Validation
- Verify symbol exists in Yahoo Finance before fetching
- Cache validation results for 24 hours
- Log warnings for symbols that fail validation

### Date Validation

#### Basic Rules
- Format: ISO 8601 (`YYYY-MM-DD`)
- Must not be in the future
- Must not be before 1990-01-01 (reasonable historical limit)
- Weekend dates allowed (will fetch last trading day data)

#### Date Range Rules
- Start date must be before end date
- Maximum range: 10 years per request (performance)
- Minimum range: 1 day

### Configuration Validation

#### symbols.json Schema Validation
```python
from jsonschema import validate

SYMBOLS_SCHEMA = {
    "type": "object",
    "required": ["symbols", "market"],
    "properties": {
        "symbols": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1000,
            "items": {"type": "string", "pattern": "^[A-Z0-9]{1,5}$"}
        },
        "market": {
            "type": "string",
            "enum": ["ASX", "NYSE", "NASDAQ"]
        },
        "update_frequency": {
            "type": "string",
            "enum": ["daily", "weekly"]
        }
    }
}
```

## Output Data Validation

### OHLCV Data Rules

#### Price Validation
1. **Non-negative**: All prices (open, high, low, close, adjusted_close) must be > 0
2. **High-Low Relationship**: `high >= max(open, close, low)`
3. **Low-High Relationship**: `low <= min(open, close, high)`
4. **Reasonable Range**: Daily price change < 50% (detects data errors)
5. **No Infinities**: Check for `inf`, `-inf`, `NaN` values

```python
def validate_ohlcv(row: dict) -> List[str]:
    """Validate OHLCV data row. Returns list of validation errors."""
    errors = []
    
    # Check non-negative
    for field in ['open', 'high', 'low', 'close', 'adjusted_close']:
        if row[field] <= 0:
            errors.append(f"{field} must be positive: {row[field]}")
    
    # Check high/low relationships
    if row['high'] < row['low']:
        errors.append(f"high ({row['high']}) must be >= low ({row['low']})")
    
    if row['high'] < row['open']:
        errors.append(f"high ({row['high']}) must be >= open ({row['open']})")
        
    if row['high'] < row['close']:
        errors.append(f"high ({row['high']}) must be >= close ({row['close']})")
    
    if row['low'] > row['open']:
        errors.append(f"low ({row['low']}) must be <= open ({row['open']})")
        
    if row['low'] > row['close']:
        errors.append(f"low ({row['low']}) must be <= close ({row['close']})")
    
    # Check for reasonable price changes
    if abs(row['close'] - row['open']) / row['open'] > 0.5:
        errors.append(f"Suspicious price change > 50%: {row}")
    
    # Check for infinities and NaN
    for field in ['open', 'high', 'low', 'close', 'adjusted_close', 'volume']:
        if not math.isfinite(row[field]):
            errors.append(f"{field} is not finite: {row[field]}")
    
    return errors
```

#### Volume Validation
- **Non-negative**: Volume must be >= 0
- **Reasonable Range**: Volume should be within 0 to 1 billion (ASX typical)
- **Zero Volume Warning**: Log warning if volume is 0 (holiday/suspension)

#### Duplicate Detection
- **Rule**: No duplicate (symbol, date) pairs
- **Action**: Log error and use most recent fetch timestamp
- **Prevention**: Check before inserting into storage

### Indicator Validation

#### General Rules
1. **Finite Values**: No `inf`, `-inf` allowed
2. **NaN Handling**: NaN allowed only in warmup period
3. **Warmup Period**: First N rows can have NaN (N = indicator period)

```python
def validate_indicator(
    df: pl.DataFrame,
    indicator_column: str,
    warmup_period: int
) -> List[str]:
    """Validate indicator column in DataFrame."""
    errors = []
    
    # Check for infinite values
    if df[indicator_column].is_infinite().any():
        errors.append(f"{indicator_column} contains infinite values")
    
    # Check NaN only in warmup period
    nan_indices = df[indicator_column].is_nan().to_list()
    for i, is_nan in enumerate(nan_indices):
        if is_nan and i >= warmup_period:
            errors.append(
                f"{indicator_column} has NaN at index {i} "
                f"(beyond warmup period {warmup_period})"
            )
    
    return errors
```

#### Indicator-Specific Rules

##### RSI (Relative Strength Index)
- **Range**: 0 <= RSI <= 100
- **Warmup**: Minimum 14 periods (configurable)

##### MACD
- **No Range Limit**: Can be any value
- **Warmup**: Minimum 26 periods

##### Bollinger Bands
- **Order**: `lower_band <= close <= upper_band` (mostly)
- **Width**: `upper_band - lower_band > 0`
- **Warmup**: Minimum 20 periods

##### Moving Averages
- **Positive**: Should match price positivity
- **Warmup**: Minimum N periods (N = MA period)

## Data Quality Checks

### Completeness Checks

#### Date Continuity
```python
def check_date_continuity(df: pl.DataFrame, symbol: str) -> List[str]:
    """Check for missing dates in data."""
    issues = []
    
    dates = sorted(df.filter(pl.col('symbol') == symbol)['date'].to_list())
    
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i-1]).days
        
        # Allow weekends and holidays (max 4 days gap)
        if delta > 4:
            issues.append(
                f"Gap detected for {symbol}: {dates[i-1]} to {dates[i]} "
                f"({delta} days)"
            )
    
    return issues
```

#### Symbol Coverage
- All configured symbols should have data for each date
- Log warning if symbol data is missing
- Track symbol availability over time

### Accuracy Checks

#### Price Spike Detection
```python
def detect_price_spikes(
    df: pl.DataFrame,
    symbol: str,
    threshold: float = 0.3
) -> List[dict]:
    """Detect abnormal price movements (>30% in one day)."""
    spikes = []
    
    symbol_df = df.filter(pl.col('symbol') == symbol).sort('date')
    
    # Calculate daily returns
    returns = symbol_df['close'].pct_change()
    
    for i, ret in enumerate(returns):
        if abs(ret) > threshold:
            spikes.append({
                'symbol': symbol,
                'date': symbol_df['date'][i],
                'return': ret,
                'close': symbol_df['close'][i],
                'prev_close': symbol_df['close'][i-1]
            })
    
    return spikes
```

#### Volume Anomaly Detection
```python
def detect_volume_anomalies(
    df: pl.DataFrame,
    symbol: str,
    std_threshold: float = 5.0
) -> List[dict]:
    """Detect volume anomalies (>5 standard deviations)."""
    anomalies = []
    
    symbol_df = df.filter(pl.col('symbol') == symbol).sort('date')
    
    # Calculate z-score for volume
    mean_volume = symbol_df['volume'].mean()
    std_volume = symbol_df['volume'].std()
    
    for row in symbol_df.iter_rows(named=True):
        z_score = (row['volume'] - mean_volume) / std_volume
        if abs(z_score) > std_threshold:
            anomalies.append({
                'symbol': symbol,
                'date': row['date'],
                'volume': row['volume'],
                'z_score': z_score
            })
    
    return anomalies
```

### Consistency Checks

#### Cross-Symbol Validation
```python
def check_market_wide_anomalies(
    df: pl.DataFrame,
    date: date,
    threshold: float = 0.8
) -> dict:
    """Check if too many symbols have anomalies on same date."""
    
    symbols = df.filter(pl.col('date') == date)['symbol'].unique()
    anomalies = 0
    
    for symbol in symbols:
        symbol_data = df.filter(
            (pl.col('symbol') == symbol) & (pl.col('date') == date)
        )
        
        # Check for various anomalies
        if has_anomaly(symbol_data):
            anomalies += 1
    
    anomaly_rate = anomalies / len(symbols)
    
    return {
        'date': date,
        'total_symbols': len(symbols),
        'anomalies': anomalies,
        'anomaly_rate': anomaly_rate,
        'is_suspicious': anomaly_rate > threshold
    }
```

#### Data Source Consistency
- Verify adjusted_close accounts for splits/dividends
- Compare with previous day's data for continuity
- Check timestamp consistency

## Automated Quality Reports

### Daily Quality Report
```python
@dataclass
class DataQualityReport:
    """Daily data quality report."""
    date: date
    total_symbols: int
    symbols_with_data: int
    validation_errors: List[dict]
    price_spikes: List[dict]
    volume_anomalies: List[dict]
    missing_symbols: List[str]
    duplicate_entries: int
    data_completeness: float  # percentage
    
    def is_healthy(self) -> bool:
        """Check if data quality is acceptable."""
        return (
            len(self.validation_errors) == 0 and
            self.data_completeness > 0.95 and
            self.duplicate_entries == 0
        )
    
    def to_json(self) -> str:
        """Export report as JSON."""
        return json.dumps(dataclasses.asdict(self), default=str)
```

### Weekly Quality Summary
- Aggregate daily reports
- Trend analysis (data quality over time)
- Alert if quality degrading
- Symbol availability statistics

## Error Handling Strategy

### Validation Failure Actions

#### Critical Errors (Stop Processing)
- Invalid symbol format in configuration
- S3 bucket not accessible
- Corrupted Parquet files
- Schema mismatch

#### Warning Errors (Log and Continue)
- Single symbol fetch failure
- Single date missing data
- Minor price anomalies
- Volume = 0

#### Correctable Errors (Auto-Fix)
- Extra whitespace in symbols (trim)
- Lowercase symbols (convert to uppercase)
- Duplicate entries (keep most recent)

### Error Logging Format
```json
{
  "timestamp": "2025-12-25T10:30:00Z",
  "severity": "ERROR",
  "error_code": "VALIDATION_FAILED",
  "message": "OHLCV validation failed for BHP on 2025-12-25",
  "details": {
    "symbol": "BHP",
    "date": "2025-12-25",
    "errors": [
      "high (50.0) must be >= low (55.0)"
    ]
  },
  "context": {
    "lambda_request_id": "abc-123",
    "function_name": "stock-data-fetcher"
  }
}
```

## Quality Metrics

### Key Performance Indicators

1. **Data Completeness**: % of expected (symbol, date) pairs present
   - Target: > 99%

2. **Validation Error Rate**: Errors per 1000 records
   - Target: < 1

3. **Data Freshness**: Time since last update
   - Target: < 24 hours for daily data

4. **Anomaly Rate**: % of records flagged as anomalies
   - Target: < 1%

5. **Duplicate Rate**: % of duplicate (symbol, date) pairs
   - Target: 0%

### Monitoring Dashboard Metrics
- Total records processed (daily)
- Validation error count (daily)
- Symbol availability (%)
- Average processing time
- Data quality score (composite metric)

## Testing Data Quality

### Unit Tests
```python
def test_validate_ohlcv_valid_data():
    """Test validation passes for valid data."""
    data = {
        'open': 50.0,
        'high': 52.0,
        'low': 49.0,
        'close': 51.0,
        'adjusted_close': 51.0,
        'volume': 1000000
    }
    errors = validate_ohlcv(data)
    assert len(errors) == 0

def test_validate_ohlcv_invalid_high_low():
    """Test validation fails when high < low."""
    data = {
        'open': 50.0,
        'high': 49.0,  # Invalid: high < low
        'low': 50.0,
        'close': 50.0,
        'adjusted_close': 50.0,
        'volume': 1000000
    }
    errors = validate_ohlcv(data)
    assert any('high' in err and 'low' in err for err in errors)
```

### Integration Tests
- Test full data quality pipeline
- Test with real historical data
- Test error recovery
- Test quality report generation
