.PHONY: help install test lint format clean build publish docs

help: ## Show help
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install development dependencies
	uv sync --dev

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=fastapi_redis_utils --cov-report=html --cov-report=term-missing

lint: ## Check code with linters
	uv run ruff check .
	uv run ruff format .
	uv run mypy .

security: ## Run security checks
	uv run bandit -r fastapi_redis_utils -f json -o bandit-report.json

format: ## Format code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

build: ## Build package
	uv build

check: ## Full pre-commit check
	uv run ruff check .
	uv run mypy fastapi_redis_utils tests/
	uv run bandit -r fastapi_redis_utils -f json -o bandit-report.json || true
	uv run pytest

example-fastapi: ## Run FastAPI example
	uv run python examples/fastapi_integration.py

dev-setup: ## Setup development environment
	uv sync --dev

version: ## Show current version
	@uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)"

tags: ## List all git tags
	@git tag --sort=-version:refname

release: ## Create release: build, test, tag and push
	@echo "Creating release for version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@make clean
	@make test
	@make build
	@make publish
	@echo "Release v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") completed successfully"

publish: ## Create and push git tag with current version
	@echo "Creating git tag for version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@git tag -a v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") -m "Release version $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@git push origin v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")
	@echo "Tag v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)") created and pushed successfully"

publish-dry-run: ## Show what would be done without creating tag
	@echo "Would create git tag: v$(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"
	@echo "Would push tag to origin"
	@echo "Current version: $(shell uv run python -c "import fastapi_redis_utils; print(fastapi_redis_utils.__version__)")"

