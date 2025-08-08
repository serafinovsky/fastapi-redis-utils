#!/usr/bin/env python3
"""
FastAPI Redis Utils integration example.

This example demonstrates:
- Creating FastAPI application with Redis
- Using dependencies for Redis client injection
- Application lifecycle event handling
- Creating API endpoints with Redis
"""

import logging
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from fastapi_redis_utils import BaseRepository, BaseResultModel, RedisManager, create_redis_client_dependencies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_redis_url() -> str:
    """Get Redis URL from environment or use default."""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{redis_host}:{redis_port}"


redis_manager = RedisManager(
    dsn=get_redis_url(),
    max_connections=20,
    retry_attempts=3,
)


get_redis_client = create_redis_client_dependencies(redis_manager)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Connecting to Redis...")
    await redis_manager.connect()
    logger.info("Redis connected")

    yield

    logger.info("Closing Redis connection...")
    await redis_manager.close()
    logger.info("Redis connection closed")


app = FastAPI(
    title="FastAPI Redis Utils Demo",
    description="FastAPI Redis integration demonstration",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check() -> dict[str, str | bool]:
    redis_healthy = await redis_manager.health_check()
    return {
        "status": "healthy" if redis_healthy else "unhealthy",
        "redis_connected": redis_healthy,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/depends/{key}")
async def get_cached_data(key: str, redis_client: Annotated[redis.Redis, Depends(get_redis_client)]) -> dict[str, str]:
    """Get data from cache."""
    value = await redis_client.get(key)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in cache",
        )

    return {"key": key, "value": value}


@app.post("/depends/{key}")
async def set_cached_data(
    key: str, value: str, redis_client: Annotated[redis.Redis, Depends(get_redis_client)]
) -> dict[str, str]:
    """Save data to cache."""
    await redis_client.set(key, value)
    return {"key": key, "value": value}


@app.delete("/depends/{key}")
async def delete_cached_data(
    key: str, redis_client: Annotated[redis.Redis, Depends(get_redis_client)]
) -> dict[str, str]:
    """Delete data from cache."""
    deleted = await redis_client.delete(key)
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in cache",
        )

    return {"key": key}


@app.get("/depends/{key}/exists")
async def check_key_exists(
    key: str, redis_client: Annotated[redis.Redis, Depends(get_redis_client)]
) -> dict[str, str | bool]:
    """Check if key exists in cache."""
    exists = await redis_client.exists(key)
    return {"key": key, "exists": bool(exists)}


# CRUD endpoints for DemoModel using DemoRepository


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


@app.post("/repo/", status_code=status.HTTP_201_CREATED)
async def create_demo(demo_model: CreateDemoSchema) -> DemoSchema:
    """Create a new demo record."""
    demo_id = str(uuid.uuid4())
    result = await demo_crud.create(demo_id, demo_model)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create demo record with ID '{demo_id}'",
        )
    return result


@app.get("/repo/{demo_id}")
async def get_demo(demo_id: UUID) -> DemoSchema:
    """Get a demo record by ID."""
    demo = await demo_crud.get(str(demo_id))
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo record with ID '{demo_id}' not found",
        )

    return demo


@app.get("/repo/")
async def list_demos(limit: int = 100) -> list[DemoSchema]:
    """List all demo records"""
    return await demo_crud.list(limit=limit)


@app.put("/repo/{demo_id}")
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
