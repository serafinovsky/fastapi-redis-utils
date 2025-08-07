import asyncio
import logging
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Async Redis manager with connection pooling and retry mechanism."""

    def __init__(
        self,
        dsn: str,
        max_connections: int = 20,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
    ):
        """
        Initialize Redis manager.

        Args:
            dsn: Redis connection DSN
            max_connections: Maximum number of connections in the pool
            retry_attempts: Number of retry attempts for connection
            retry_delay: Base delay between retry attempts
            socket_connect_timeout: Socket connection timeout in seconds
            socket_timeout: Socket operation timeout in seconds
        """
        self.dsn = dsn
        self.max_connections = max_connections
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_timeout = socket_timeout

        self.redis_client: redis.Redis | None = None
        self._connection_pool: redis.ConnectionPool | None = None
        self._is_connected: bool = False

    async def connect(self) -> None:
        """Create Redis connection with retry mechanism."""
        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"Attempting to connect to Redis (attempt {attempt + 1}/{self.retry_attempts})")

                self._connection_pool = redis.ConnectionPool.from_url(
                    self.dsn,
                    decode_responses=True,
                    max_connections=self.max_connections,
                    retry_on_timeout=True,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_timeout=self.socket_timeout,
                )

                self.redis_client = redis.Redis(connection_pool=self._connection_pool)

                await self.redis_client.ping()
                self._is_connected = True

                logger.info("Successfully connected to Redis")
                return

            except Exception as e:
                logger.error(f"Failed to connect to Redis (attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    self._is_connected = False
                    raise ConnectionError(
                        f"Failed to connect to Redis after {self.retry_attempts} attempts: {e}"
                    ) from e

    async def ensure_connection(self) -> None:
        """Ensure Redis connection is available."""
        if not self._is_connected:
            await self.connect()

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        self._is_connected = False
        if self.redis_client:
            try:
                await self.redis_client.aclose()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.redis_client = None

        if self._connection_pool:
            try:
                await self._connection_pool.disconnect()
                logger.info("Redis connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection pool: {e}")
            finally:
                self._connection_pool = None

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        This method can be used for external monitoring/metrics collection.
        """
        if not self.redis_client or not self._is_connected:
            return False

        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.exception(f"Redis health check failed: {e}")
            self._is_connected = False
            return False

    def get_client(self) -> redis.Redis:
        """Get Redis client instance with connection validation."""
        if not self.redis_client or not self._is_connected:
            raise RuntimeError("Redis client not initialized or disconnected. Call connect() first.")
        return self.redis_client

    async def execute_with_retry(self, operation: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute Redis operation with retry mechanism."""
        for attempt in range(self.retry_attempts):
            try:
                if not self._is_connected:
                    await self.connect()
                return await operation(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Redis operation failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
