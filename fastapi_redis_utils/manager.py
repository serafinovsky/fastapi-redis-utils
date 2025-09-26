import asyncio
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Async Redis manager with connection pooling."""

    def __init__(
        self,
        dsn: str,
        max_connections: int = 20,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
    ):
        """
        Initialize Redis manager.

        Args:
            dsn: Redis connection DSN
            max_connections: Maximum number of connections in the pool
            socket_connect_timeout: Socket connection timeout in seconds
            socket_timeout: Socket operation timeout in seconds
        """
        self.dsn = dsn
        self.max_connections = max_connections
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_timeout = socket_timeout

        self.redis_client: redis.Redis | None = None
        self._connection_pool: redis.ConnectionPool | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

    async def connect(self) -> None:
        """Create Redis connection."""
        async with self._lock:
            if self.redis_client is not None:
                return

            try:
                logger.info("Connecting to Redis")
                connection_pool = redis.ConnectionPool.from_url(
                    self.dsn,
                    decode_responses=True,
                    max_connections=self.max_connections,
                    retry_on_timeout=True,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_timeout=self.socket_timeout,
                )

                client = redis.Redis(connection_pool=connection_pool)

                await client.ping()
                self._connection_pool = connection_pool
                self.redis_client = client

                logger.info("Successfully connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self.redis_client = None

        if self._connection_pool:
            try:
                await self._connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error closing Redis connection pool: {e}")
            finally:
                self._connection_pool = None

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        This method can be used for external monitoring/metrics collection.
        """
        if not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.exception(f"Redis health check failed: {e}")
            return False

    def get_client(self) -> redis.Redis:
        """Get Redis client instance."""
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized or disconnected. Call connect() first.")
        return self.redis_client
