import fakeredis.aioredis
import pytest
import redis.asyncio as redis
from fakeredis import FakeServer
from fakeredis.aioredis import FakeConnection
from redis.asyncio.connection import ConnectionPool

from fastapi_redis_utils import RedisManager


@pytest.fixture
async def fake_redis_server():
    """Create a fake Redis server for testing."""
    server = FakeServer()
    return server


@pytest.fixture
async def fake_redis_client(fake_redis_server):
    """Create a fake Redis client for testing."""
    client = fakeredis.aioredis.FakeRedis(server=fake_redis_server)
    return client


@pytest.fixture
def redis_manager_with_fake():
    """Create RedisManager with fake Redis configuration."""
    return RedisManager(
        dsn="redis://localhost:6379",
        max_connections=10,
        retry_attempts=2,
        retry_delay=0.1,
    )


@pytest.fixture
async def connected_redis_manager(fake_redis_server):
    """Create a RedisManager connected to fake Redis."""
    manager = RedisManager(
        dsn="redis://localhost:6379",
        max_connections=10,
        retry_attempts=2,
        retry_delay=0.1,
    )

    # Create connection pool with fake Redis
    connection_pool = ConnectionPool(
        server=fake_redis_server,
        connection_class=FakeConnection,
        decode_responses=True,
        max_connections=10,
    )

    # Create Redis client with fake connection pool
    fake_client = redis.Redis(connection_pool=connection_pool)

    # Patch the manager to use fake Redis
    with pytest.MonkeyPatch().context() as m:
        m.setattr(manager, "redis_client", fake_client)
        m.setattr(manager, "_connection_pool", connection_pool)
        m.setattr(manager, "_is_connected", True)

        yield manager
        await manager.close()
