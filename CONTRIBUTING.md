# Contributing to the Project

Thank you for your interest in the FastAPI Redis Connection project! We welcome contributions from the community.

## How to Contribute

### 1. Fork the Repository

1. Go to the [GitHub repository](https://github.com/serafinovsky/fastapi-redis-utils)
2. Click the "Fork" button in the top right corner
3. Clone your fork locally:

```bash
git clone https://github.com/serafinovsky/fastapi-redis-utils.git
cd fastapi-redis-utils
```

### 2. Set Up Development Environment

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --dev

# Install pre-commit hooks (optional)
uv run pre-commit install
```

### 3. Create a Branch for Your Changes

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 4. Make Your Changes

- Write code following the existing style
- Add tests for new features
- Update documentation when necessary
- Follow [Conventional Commits](https://www.conventionalcommits.org/) principles

### 5. Run Tests and Checks

```bash
# Run all checks
make check

# Or individually:
uv run pytest          # Tests
uv run ruff check .    # Linting and formatting
uv run mypy .          # Type checking
```

### 6. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature"
git push origin feature/your-feature-name
```

### 7. Create a Pull Request

1. Go to GitHub in your fork
2. Click "New Pull Request"
3. Select the branch with your changes
4. Fill out the PR template
5. Wait for CI/CD checks

## Code Standards

### Code Style

- Use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)

### Type Hints

- Use type hints for all functions and methods
- Add types for variables where it improves readability
- Use [mypy](http://mypy-lang.org/) for type checking

### Testing

- Cover new code with tests
- Use [pytest](https://docs.pytest.org/) for testing
- Aim for at least 90% code coverage
- Write tests for async code with `pytest-asyncio`

### Documentation

- Update docstrings for new functions
- Update README.md when changing the API
- Add usage examples

## Project Structure

```text
fastapi-redis-utils/
├── fastapi_redis_utils/    # Main package code
│   ├── __init__.py
│   ├── manager.py               # RedisManager
│   └── dependency.py            # FastAPI dependencies
├── tests/                       # Tests
│   ├── test_manager.py
│   └── test_dependency.py
├── examples/                    # Usage examples
│   ├── basic_usage.py
│   └── fastapi_integration.py
├── .github/workflows/           # CI/CD
├── pyproject.toml              # Project configuration
├── README.md                   # Documentation
└── LICENSE                     # License
```

## Release Process

### Preparing for Release

1. Update the version in `fastapi_redis_utils/__init__.py`
2. Update `CHANGELOG.md` (if exists)
3. Ensure all tests pass
4. Verify documentation is up to date

### Creating a Release

1. Create a version tag:

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. Create a release on GitHub:

   - Go to "Releases" on GitHub
   - Click "Create a new release"
   - Select the created tag
   - Fill in the release description

3. CI/CD will automatically publish the package to PyPI

## Getting Help

- Create an [Issue](https://github.com/serafinovsky/fastapi-redis-utils/issues) for bugs or suggestions
- Discuss changes in an Issue before creating a PR
- Join discussions in existing Issues

## License

By contributing to the project, you agree that your contribution will be licensed under the same MIT license as the project.
