from collections.abc import Awaitable, Callable

import redis.asyncio as redis

from .manager import RedisManager


def create_redis_client_dependencies(redis_manager: RedisManager) -> Callable[[], Awaitable[redis.Redis]]:
    """
    Create FastAPI dependency for Redis manager.

    Args:
        redis_manager: RedisManager instance

    Returns:
        get_redis_client function
    """

    async def get_redis_client() -> redis.Redis:
        """Dependency to get Redis client instance"""
        return redis_manager.get_client()

    return get_redis_client
