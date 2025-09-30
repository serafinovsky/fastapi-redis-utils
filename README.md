# FastAPI Redis Utils

[![Publish](https://img.shields.io/github/actions/workflow/status/serafinovsky/fastapi-redis-utils/release-please.yml)](https://github.com/serafinovsky/fastapi-redis-utils/actions/workflows/release-please.yml)
[![codecov](https://codecov.io/gh/serafinovsky/fastapi-redis-utils/branch/main/graph/badge.svg)](https://codecov.io/gh/serafinovsky/fastapi-redis-utils)
[![PyPI](https://img.shields.io/pypi/v/fastapi-redis-utils.svg)](https://pypi.org/project/fastapi-redis-utils/)
[![Downloads](https://pepy.tech/badge/fastapi-redis-utils)](https://pepy.tech/project/fastapi-redis-utils)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/serafinovsky/fastapi-redis-utils)](https://github.com/serafinovsky/fastapi-redis-utils/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-redis-utils)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked with mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](http://mypy-lang.org/)
[![Security: bandit](https://img.shields.io/badge/security-bandit-green.svg)](https://github.com/PyCQA/bandit)

**Fast and easy Redis integration for FastAPI applications.**

This library provides everything you need to quickly integrate Redis with FastAPI:

- **RedisManager** - Async Redis manager with connection pooling
- **FastAPI Dependencies** - Ready-to-use dependencies for Redis injection into your endpoints
- **BaseRepository** - CRUD operations with Pydantic models for rapid development

Perfect for caching, session storage, and data persistence in FastAPI applications.

## Features

- **FastAPI Integration** - Ready-to-use dependencies for Redis injection
- **Async Support** - Full async/await capabilities
- **Connection Management** - Efficient connection pooling
- **Monitoring** - Built-in connection health checks
- **Type Hints** - Complete typing support
- **Pydantic Models** - Base repository with Pydantic support

## Documentation

- **[Usage Guide](https://github.com/serafinovsky/fastapi-redis-utils/blob/main/USAGE.md)**
- **[FastAPI Integration Example](https://github.com/serafinovsky/fastapi-redis-utils/blob/main/examples/fastapi_integration.py)** - Complete FastAPI application with Redis integration

## Installation

### From PyPI

```bash
uv add fastapi-redis-utils
```

### From Git repository

```bash
uv add git+https://github.com/serafinovsky/fastapi-redis-utils.git
```

## Quick Start

### FastAPI Integration

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi_redis_utils import RedisManager, create_redis_client_dependencies
import redis.asyncio as redis

# Create Redis manager
redis_manager = RedisManager(
    dsn="redis://localhost:6379"
)

# Create FastAPI dependency
get_redis_client = create_redis_client_dependencies(redis_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    try:
        yield
    finally:
        await redis_manager.close()

app = FastAPI(lifespan=lifespan)

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

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import HTTPException, status
from fastapi_redis_utils import BaseRepository, BaseResultModel
from fastapi import FastAPI
from fastapi_redis_utils import RedisManager
from pydantic import BaseModel

# Create Redis manager
redis_manager = RedisManager(
    dsn="redis://localhost:6379"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    try:
        yield
    finally:
        await redis_manager.close()

app = FastAPI(lifespan=lifespan)

class CreateDemoSchema(BaseModel):
    field1: str
    field2: str


class UpdateDemoSchema(BaseModel):
    field1: str | None = None
    field2: str | None = None


class DemoSchema(BaseResultModel):
    key: str | None = None
    field1: str
    field2: str

    def set_key(self, key: str) -> None:
        self.key = key


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

## Configuration

### RedisManager Parameters

| Parameter                | Type | Default | Description                           |
| ------------------------ | ---- | ------- | ------------------------------------- |
| `dsn`                    | str  | `-`     | DSN for Redis connection              |
| `max_connections`        | int  | `20`    | Maximum number of connections in pool |
| `socket_connect_timeout` | int  | `5`     | Socket connection timeout (seconds)   |
| `socket_timeout`         | int  | `5`     | Socket operation timeout (seconds)    |

## API Reference

### RedisManager

Main class for managing Redis connections.

#### Methods

- `connect()` - Connect to Redis
- `close()` - Close connection and cleanup resources
- `health_check()` - Check connection status
- `get_client()` - Get Redis client

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

---

Repository initiated with [serafinovsky/cookiecutter-python-package](https://github.com/serafinovsky/cookiecutter-python-package)
