import os

import pytest
import redis.asyncio as redis

from fastapi_redis_utils import RedisManager


@pytest.fixture(scope="session")
def get_redis_url():
    """Get Redis URL from environment or use default."""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{redis_host}:{redis_port}"


@pytest.fixture(autouse=True)
async def clean_redis(get_redis_url: str):
    """Clean Redis before each test."""
    client = redis.Redis.from_url(get_redis_url, decode_responses=True)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture
def redis_manager(get_redis_url: str):
    """Create RedisManager with configuration."""
    return RedisManager(
        dsn=get_redis_url,
        max_connections=10,
        retry_attempts=5,
        retry_delay=0.5,
    )


@pytest.fixture
async def connected_redis_manager(get_redis_url: str):
    """Create a RedisManager connected to real Redis with clean state."""
    manager = RedisManager(
        dsn=get_redis_url,
        max_connections=10,
        retry_attempts=5,
        retry_delay=0.5,
    )

    try:
        await manager.connect()
        yield manager
    finally:
        await manager.close()
