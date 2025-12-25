.PHONY: help install install-dev test test-unit test-integration lint format type-check package deploy clean

help:
	@echo "Stock Stream 2 - Makefile Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linting (ruff)"
	@echo "  make format           Format code (ruff format)"
	@echo "  make type-check       Run type checking (mypy)"
	@echo "  make check-all        Run all checks (lint + type-check)"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests (requires AWS)"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo ""
	@echo "Deployment:"
	@echo "  make package          Package Lambda functions"
	@echo "  make deploy           Deploy infrastructure with Terraform"
	@echo "  make destroy          Destroy infrastructure"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            Clean build artifacts and cache"
	@echo "  make clean-all        Clean everything including virtual env"
	@echo "  make bootstrap        Bootstrap initial data and config"

# Setup & Installation

install:
	@echo "Installing production dependencies..."
	uv pip install -e .

install-dev:
	@echo "Installing development dependencies..."
	uv pip install -e ".[dev]"
	@echo "Setting up pre-commit hooks..."
	pre-commit install

# Code Quality

lint:
	@echo "Running ruff linter..."
	ruff check modules/ tests/ scripts/

format:
	@echo "Formatting code with ruff..."
	ruff format modules/ tests/ scripts/
	@echo "Sorting imports..."
	ruff check --select I --fix modules/ tests/ scripts/

type-check:
	@echo "Running mypy type checker..."
	mypy modules/ tests/ scripts/

check-all: lint type-check
	@echo "All checks passed!"

# Testing

test:
	@echo "Running all tests..."
	pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests (requires AWS credentials)..."
	pytest tests/integration/ -v --aws

test-coverage:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=modules --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

# Deployment

package:
	@echo "Packaging Lambda functions..."
	mkdir -p lambda_packages
	@echo "Packaging stock_data_fetcher..."
	cd modules/stock_data_fetcher && \
		pip install -r requirements.txt -t ../../lambda_packages/stock_data_fetcher && \
		cp -r . ../../lambda_packages/stock_data_fetcher/ && \
		cd ../../lambda_packages && \
		cd stock_data_fetcher && zip -r ../stock_data_fetcher.zip . && cd ..
	@echo "Packaging asx_symbol_updater..."
	cd modules/asx_symbol_updater && \
		pip install -r requirements.txt -t ../../lambda_packages/asx_symbol_updater && \
		cp -r . ../../lambda_packages/asx_symbol_updater/ && \
		cd ../../lambda_packages && \
		cd asx_symbol_updater && zip -r ../asx_symbol_updater.zip . && cd ..
	@echo "Lambda packages created in lambda_packages/"

deploy:
	@echo "Deploying infrastructure with Terraform..."
	cd terraform && \
		terraform init && \
		terraform plan -out=tfplan && \
		terraform apply tfplan
	@echo "Deployment complete!"

deploy-auto:
	@echo "Deploying infrastructure (auto-approve)..."
	cd terraform && terraform apply -auto-approve

destroy:
	@echo "WARNING: This will destroy all infrastructure!"
	@echo "Press Ctrl+C to cancel, or wait 10 seconds to continue..."
	@sleep 10
	cd terraform && terraform destroy

# Utilities

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf lambda_packages/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf **/__pycache__
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "Clean complete!"

clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf .venv/
	@echo "Removing data and cache..."
	rm -rf data/
	rm -rf .cache/
	rm -rf backtest_results/
	@echo "All cleaned!"

bootstrap:
	@echo "Bootstrapping project..."
	@echo "Creating directories..."
	mkdir -p config data scripts logs backtest_results
	@echo "Creating initial symbols config..."
	@if [ ! -f config/symbols.json ]; then \
		echo '{"symbols": ["BHP", "CBA", "NAB", "WBC", "ANZ"], "market": "ASX"}' > config/symbols.json; \
		echo "Created config/symbols.json"; \
	else \
		echo "config/symbols.json already exists"; \
	fi
	@echo "Bootstrap complete!"

# Development utilities

run-fetcher-local:
	@echo "Running stock data fetcher locally..."
	python -m modules.stock_data_fetcher.main --config config/symbols.json --output data/

run-updater-local:
	@echo "Running ASX symbol updater locally..."
	python -m modules.asx_symbol_updater.main

backtest-example:
	@echo "Running example backtest..."
	python -m scripts.local_backtest \
		--strategy MovingAverageCrossover \
		--symbols BHP,CBA \
		--start-date 2023-01-01 \
		--end-date 2024-12-31 \
		--initial-capital 100000

data-quality-check:
	@echo "Running data quality check..."
	python -m scripts.data_quality_check

# Docker (optional)

docker-build:
	@echo "Building Docker image..."
	docker build -t stock-stream-2:latest .

docker-run:
	@echo "Running in Docker..."
	docker run -it --rm \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/.env:/app/.env \
		stock-stream-2:latest

# Documentation

docs-build:
	@echo "Building documentation..."
	cd docs && make html
	@echo "Documentation built in docs/_build/html/index.html"

docs-serve:
	@echo "Serving documentation..."
	python -m http.server --directory docs/_build/html 8000
