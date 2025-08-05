# FastAPI Redis Utils

Async Redis manager with FastAPI integration, connection pooling and retry mechanism.

## Features

- 🔄 **Async-first** - Full async/await support
- 🏊 **Connection pooling** - Efficient connection management
- 🔁 **Retry mechanism** - Automatic retries on failures
- ⚡ **FastAPI integration** - Ready-to-use FastAPI dependencies
- 🏥 **Health check** - Built-in connection status monitoring
- 🛡️ **Type safety** - Full type hints support
- 📦 **BaseRepository** - Base repository class with Pydantic model support

## Documentation

- 📖 **[Usage Guide](USAGE.md)** - Detailed usage examples and advanced features
- 🚀 **[FastAPI Integration Example](examples/fastapi_integration.py)** - Complete FastAPI application with Redis integration

## Installation

### From PyPI

```bash
uv add fastapi-redis-utils
```

### From Git repository

```bash
uv add git+https://github.com/serafinovsky/fastapi-redis-utils.git
```

### For development

```bash
git clone https://github.com/serafinovsky/fastapi-redis-utils.git
cd fastapi-redis-utils
uv sync --dev
```

## Quick Start

### Basic Usage

```python
import asyncio
from fastapi_redis_utils import RedisManager

async def main():
    # Create manager
    redis_manager = RedisManager(
        dsn="redis://localhost:6379",
        max_connections=20,
        retry_attempts=3
    )

    # Connect
    await redis_manager.connect()

    # Use
    client = redis_manager.get_client()
    await client.set("key", "value")
    value = await client.get("key")

    # Close
    await redis_manager.close()

asyncio.run(main())
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from fastapi_redis_utils import RedisManager, create_redis_client_dependencies
import redis.asyncio as redis

app = FastAPI()

# Create Redis manager
redis_manager = RedisManager(
    dsn="redis://localhost:6379"
)

# Create FastAPI dependency
get_redis_client = create_redis_client_dependencies(redis_manager)

@app.on_event("startup")
async def startup_event():
    """Connect to Redis on application startup"""
    await redis_manager.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close connection on application shutdown"""
    await redis_manager.close()

@app.get("/cache/{key}")
async def get_cached_data(key: str, redis_client: redis.Redis = Depends(get_redis_client)):
    """Get data from cache"""
    value = await redis_client.get(key)
    return {"key": key, "value": value}

@app.post("/cache/{key}")
async def set_cached_data(
    key: str,
    value: str,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Save data to cache"""
    await redis_client.set(key, value)
    return {"key": key, "value": value, "status": "saved"}

@app.get("/health")
async def health_check():
    """Check Redis connection status"""
    is_healthy = await redis_manager.health_check()
    return {"redis_healthy": is_healthy}
```

### Using BaseRepository with Separate Create and Update Schemas

```python
import uuid
from uuid import UUID
from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from fastapi_redis_utils import BaseRepository, RedisManager, BaseResultModel

class CreateDemoSchema(BaseModel):
    field1: str
    field2: str


class UpdateDemoSchema(BaseModel):
    field1: str | None = None
    field2: str | None = None


class DemoSchema(BaseResultModel):
    id: str | None = None
    field1: str
    field2: str

    def set_id(self, id: str) -> None:
        self.id = id


class DemoRepository(BaseRepository[CreateDemoSchema, UpdateDemoSchema, DemoSchema]):
    pass


demo_crud = DemoRepository(redis_manager, CreateDemoSchema, UpdateDemoSchema, DemoSchema)


@app.post("/repo/", response_model=DemoSchema, status_code=status.HTTP_201_CREATED)
async def create_demo(demo_model: CreateDemoSchema) -> DemoSchema:
    """Create a new demo record."""
    demo_id = str(uuid.uuid4())
    return await demo_crud.create(demo_id, demo_model)


@app.get("/repo/{demo_id}", response_model=DemoSchema)
async def get_demo(demo_id: UUID) -> DemoSchema:
    """Get a demo record by ID."""
    demo = await demo_crud.get(str(demo_id))
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo record with ID '{demo_id}' not found",
        )

    return demo


@app.get("/repo/", response_model=list[DemoSchema])
async def list_demos(limit: int = 100) -> list[DemoSchema]:
    """List all demo records"""
    return await demo_crud.list(limit=limit)


@app.put("/repo/{demo_id}", response_model=DemoSchema)
async def update_demo(demo_id: UUID, demo_update: UpdateDemoSchema) -> DemoSchema:
    """Update a demo record."""
    updated_demo = await demo_crud.update(str(demo_id), demo_update)
    if updated_demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo record with ID '{demo_id}' not found",
        )
    return updated_demo


@app.delete("/repo/{demo_id}")
async def delete_demo(demo_id: UUID) -> dict[str, UUID]:
    """Delete a demo record."""
    deleted = await demo_crud.delete(str(demo_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo record with ID '{demo_id}' not found",
        )
    return {"id": demo_id}


@app.get("/repo/{demo_id}/exists")
async def check_demo_exists(demo_id: UUID) -> dict[str, UUID | bool]:
    """Check if a demo record exists."""
    exists = await demo_crud.exists(str(demo_id))
    return {"id": demo_id, "exists": exists}
```

### Executing Operations with Retry

```python
async def complex_operation():
    async def operation():
        client = redis_manager.get_client()
        # Complex Redis operation
        result = await client.execute_command("COMPLEX_COMMAND")
        return result

    # Automatic retries on failures
    result = await redis_manager.execute_with_retry(operation)
    return result
```

## Configuration

### RedisManager Parameters

| Parameter                | Type  | Default | Description                           |
| ------------------------ | ----- | ------- | ------------------------------------- |
| `dsn`                    | str   | `-`     | DSN for Redis connection              |
| `max_connections`        | int   | `20`    | Maximum number of connections in pool |
| `retry_attempts`         | int   | `3`     | Number of reconnection attempts       |
| `retry_delay`            | float | `1.0`   | Base delay between attempts (seconds) |
| `socket_connect_timeout` | int   | `5`     | Socket connection timeout (seconds)   |
| `socket_timeout`         | int   | `5`     | Socket operation timeout (seconds)    |

## API Reference

### RedisManager

Main class for managing Redis connections.

#### Methods

- `connect()` - Connect to Redis with retry mechanism
- `ensure_connection()` - Ensure connection availability
- `close()` - Close connection and cleanup resources
- `health_check()` - Check connection status
- `get_client()` - Get Redis client
- `execute_with_retry()` - Execute operations with retry

### create_redis_client_dependencies

Creates FastAPI dependency for getting Redis client.

### BaseRepository

Base repository class for working with Pydantic models in Redis. Supports separate schemas for create, update, and result operations with partial updates.

#### Generic Parameters

- `CreateSchemaType` - Pydantic model for create operations
- `UpdateSchemaType` - Pydantic model for update operations (all fields optional)
- `ResultSchemaType` - Pydantic model for result operations (must inherit from BaseResultModel)

#### Core Methods

- `create(key, data: CreateSchemaType, ttl=None)` - Create record
- `get(key)` - Get record (returns ResultSchemaType)
- `update(key, data: UpdateSchemaType, ttl=None)` - Update record with partial update (only set fields)
- `delete(key)` - Delete record
- `exists(key)` - Check record existence
- `list(pattern="*", limit=None)` - Get list of records
- `count(pattern="*")` - Count records
- `set_ttl(key, ttl)` - Set TTL
- `get_ttl(key)` - Get TTL
- `clear(pattern="*")` - Clear records

#### Partial Update Feature

The `update` method performs partial updates - only fields that are set in the update schema will be modified. Fields with `None` values are ignored.

## Development

### Install development dependencies

```bash
uv sync --dev
```

### Run tests

```bash
uv run pytest
```

### Code checks

```bash
uv run ruff check .
uv run mypy .
```

### Build package

```bash
uv run build
```

### Makefile Commands

The project includes convenient Makefile commands for development:

```bash
# Main commands
make install          # Install development dependencies
make test            # Run tests
make lint            # Check code with linters
make format          # Format code
make build           # Build package
make clean           # Clean temporary files

# Version management
make version         # Show current version

# Publishing
make publish         # Create and push git tag with current version
make publish-dry-run # Show what would be done without creating tag
make release         # Full release: build, test, tag and push

# Additional commands
make tags            # List all git tags
make check           # Full pre-commit check
make example-fastapi # Run FastAPI example
```

### Release Workflow

1. Update version in `fastapi_redis_utils/__init__.py`
2. Run full release: `make release`
3. Or step by step:

```bash
make test          # Run tests
make build         # Build package
make publish       # Create and push tag
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
