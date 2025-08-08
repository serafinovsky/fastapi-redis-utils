.PHONY: help install test lint format clean build publish

help: ## Show help
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: ## Run tests in Docker container with Redis
	@echo "Building and running tests in Docker..."
	@docker compose down -v
	@docker compose build app
	@docker compose run --rm app uv run pytest
	@docker compose down -v

test-cov: ## Run tests with coverage in Docker container
	@echo "Building and running tests with coverage in Docker..."
	@docker compose down -v
	@docker compose build app
	@touch coverage.xml
	@docker compose run -v ./coverage.xml:/app/coverage.xml --rm app uv run pytest --cov=fastapi_redis_utils --cov-report=term-missing --cov-report=xml --cov-config=pyproject.toml
	@docker compose down -v

lint: ## Check code with linters
	uv run ruff check . --preview
	uv run ruff format .
	uv run mypy .

security: ## Run security checks
	@uv run bandit -r fastapi_redis_utils -f json -o bandit-report.json

format: ## Format code
	uv run ruff format .
	uv run ruff check . --preview --fix

clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "bandit-report.json" -delete
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

build: ## Build package
	uv build

check: ## Full pre-commit check
	@make lint
	@make test

example-fastapi: ## Run FastAPI example
	@docker compose build app
	@docker compose run -p 8000:8000 --rm app uv run python examples/fastapi_integration.py
	@docker compose down -v

dev-setup: ## Setup development environment
	@uv sync --dev

version: ## Show current version
	@uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)"

tags: ## List all git tags
	@git tag --sort=-version:refname

release: ## Create release: build, test, tag and push
	@echo "Creating release for version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@make clean
	@make test
	@make publish
	@echo "Release v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") completed successfully"

publish: ## Create and push git tag with current version
	@echo "Creating git tag for version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@git tag -a v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") -m "Release version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@git push origin v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")
	@echo "Tag v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") created and pushed successfully"
