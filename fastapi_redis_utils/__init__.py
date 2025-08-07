"""
FastAPI Redis Utils

Async Redis manager with FastAPI integration, connection pooling and retry mechanism.
"""

__version__ = "1.0.5"

from .dependency import create_redis_client_dependencies
from .manager import RedisManager
from .models import BaseResultModel
from .repository import BaseRepository

__all__ = ["RedisManager", "create_redis_client_dependencies", "BaseRepository", "BaseResultModel"]
