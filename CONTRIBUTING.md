# Contributing to Stock Stream 2

Thank you for your interest in contributing to Stock Stream 2! This document provides guidelines and instructions for contributing.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

### Our Pledge
We are committed to providing a welcoming and inclusive environment for all contributors.

### Expected Behavior
- Be respectful and professional
- Accept constructive criticism gracefully
- Focus on what's best for the project
- Show empathy towards other contributors

### Unacceptable Behavior
- Harassment or discriminatory language
- Personal attacks or trolling
- Publishing private information
- Unprofessional conduct

## Getting Started

### Prerequisites
- Python 3.12+
- uv package manager
- AWS account (for testing)
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/stock-stream-2.git
   cd stock-stream-2
   ```

2. **Create Virtual Environment**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   # Core dependencies
   uv pip install polars pyarrow boto3 yfinance requests beautifulsoup4 python-dotenv loguru

   # Development dependencies (testing, linting, type checking)
   uv pip install pytest pytest-cov pytest-mock mypy ruff black moto
   ```

4. **Test Locally First (Recommended)**
   ```bash
   # Test ASX Symbol Updater with mock data (no AWS required)
   python scripts/run_asx_updater_local.py
   
   # You should see: ✅ SUCCESS with batch information
   ```

5. **Set Up Environment (for AWS testing)**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials if testing with real S3
   ```

6. **Install Pre-commit Hooks (Optional)**
   ```bash
   pre-commit install  # If you have pre-commit installed
   ```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or changes

### 2. Make Changes
- Follow the coding standards (see below)
- Write tests for new functionality
- Update documentation as needed
- Keep commits atomic and well-described

### 3. Test Your Changes
```bash
# Quick local test with mock data (no AWS required)
python scripts/run_asx_updater_local.py

# Run unit tests (when available)
pytest tests/unit -v

# Run all tests
pytest tests/ -v

# Check code quality
ruff check modules/

# Type checking
mypy modules/

# Format code
black modules/ tests/ scripts/
```
make format
```

### 4. Commit Changes
```bash
git add .
git commit -m "type: brief description

Detailed description of what changed and why.

Fixes #issue_number"
```

Commit message types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Build process or auxiliary tool changes

### 5. Push and Create PR
```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Coding Standards

### Python Style
We follow PEP 8 with some modifications:

- **Line length:** 100 characters (not 79)
- **Formatter:** ruff format
- **Linter:** ruff
- **Type checker:** mypy

### Code Quality Requirements
```bash
# All of these must pass:
make lint          # No linting errors
make type-check    # No type errors
make test          # All tests passing
make format        # Code formatted correctly
```

### Type Hints
All functions must have type hints:

```python
def fetch_stock_data(symbol: str, date: date) -> pl.DataFrame:
    """Fetch stock data for a symbol on a specific date.
    
    Args:
        symbol: Stock symbol (e.g., 'BHP')
        date: Date to fetch data for
        
    Returns:
        DataFrame with OHLCV data
        
    Raises:
        ValueError: If symbol is invalid
        ConnectionError: If API request fails
    """
    pass
```

### Docstrings
Use Google-style docstrings for all public functions, classes, and modules:

```python
"""Module for fetching stock data from Yahoo Finance.

This module provides utilities for:
- Fetching historical stock data
- Handling rate limits
- Validating and cleaning data
"""

class StockFetcher:
    """Fetches stock data with rate limiting and error handling.
    
    Attributes:
        rate_limit_delay: Seconds to wait between requests
        max_retries: Maximum number of retry attempts
    """
    
    def fetch(self, symbol: str) -> dict:
        """Fetch data for a single symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with OHLCV data
            
        Raises:
            RateLimitError: If rate limit exceeded
            ValueError: If symbol invalid
        """
        pass
```

### Error Handling
- Use specific exception types
- Always log errors with context
- Clean up resources in finally blocks
- Fail fast on invalid input

```python
def process_data(symbol: str) -> None:
    """Process stock data with proper error handling."""
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    
    try:
        data = fetch_data(symbol)
        validate_data(data)
        store_data(data)
    except RateLimitError as e:
        logger.warning(f"Rate limited on {symbol}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to process {symbol}: {e}")
        raise
```

## Testing Requirements

### Test Coverage
- Minimum 80% code coverage for new code
- 100% coverage for critical paths (data validation, order execution)

### Test Structure
```
tests/
├── unit/              # Unit tests (fast, no external dependencies)
│   ├── test_fetcher.py
│   └── test_validators.py
├── integration/       # Integration tests (with mocked AWS)
│   ├── test_lambda.py
│   └── test_s3.py
└── fixtures/          # Test data
    └── sample_data.parquet
```

### Writing Tests
```python
import pytest
from unittest.mock import Mock, patch

def test_fetch_stock_data_success():
    """Test successful stock data fetch."""
    fetcher = StockFetcher()
    data = fetcher.fetch("BHP")
    
    assert not data.empty
    assert "close" in data.columns
    assert "volume" in data.columns

def test_fetch_stock_data_invalid_symbol():
    """Test fetch with invalid symbol raises ValueError."""
    fetcher = StockFetcher()
    
    with pytest.raises(ValueError, match="Invalid symbol"):
        fetcher.fetch("")

@patch('yfinance.download')
def test_fetch_handles_rate_limit(mock_download):
    """Test rate limit handling."""
    mock_download.side_effect = RateLimitError("Too many requests")
    fetcher = StockFetcher()
    
    with pytest.raises(RateLimitError):
        fetcher.fetch("BHP")
```

### Integration Tests
Mark integration tests appropriately:

```python
@pytest.mark.integration
@pytest.mark.aws
def test_lambda_execution_with_s3():
    """Test Lambda function can write to S3."""
    # Test with mocked AWS services
    pass
```

## Submitting Changes

### Pull Request Process

1. **Update Documentation**
   - Update README.md if needed
   - Add docstrings to new functions
   - Update API_SPECIFICATION.md if interfaces changed

2. **Ensure Quality**
   ```bash
   make check-all  # Runs all quality checks
   make test       # All tests passing
   ```

3. **Create Pull Request**
   - Use descriptive title
   - Reference related issues
   - Describe what changed and why
   - Include screenshots if UI changes

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests added and passing

## Related Issues
Fixes #issue_number
```

### Review Process
1. **Automated Checks:** All CI checks must pass
2. **Code Review:** At least one approval required
3. **Testing:** Reviewer will test changes
4. **Merge:** Maintainer will merge approved PRs

### After Merge
- Delete your branch
- Update your fork
- Close related issues

## Development Tips

### Running Locally
```bash
# Fetch data locally (no Lambda)
python -m scripts.fetch_data_local --symbols BHP,CBA

# Run backtest
python -m scripts.local_backtest --strategy MovingAverageCrossover

# Check data quality
python -m scripts.data_quality_check
```

### Debugging
```bash
# Verbose logging
export LOG_LEVEL=DEBUG

# Run single test
pytest tests/unit/test_fetcher.py::test_fetch_success -v

# Debug with ipdb
pip install ipdb
# Add: import ipdb; ipdb.set_trace()
```

### Performance Testing
```bash
# Profile code
python -m cProfile -o output.prof script.py
python -m pstats output.prof

# Memory profiling
pip install memory_profiler
python -m memory_profiler script.py
```

## Questions or Issues?

- **Bugs:** Open an issue with reproduction steps
- **Features:** Open an issue to discuss before implementing
- **Questions:** Use GitHub Discussions
- **Security:** Email security@example.com (do not open public issue)

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Git commit history

Thank you for contributing to Stock Stream 2! 🚀
