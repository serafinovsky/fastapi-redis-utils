__version__ = "1.1.0"

from .dependency import create_redis_client_dependencies
from .exceptions import (
    DeserializationError,
    NotFoundError,
    RepositoryError,
    ResultModelCreationError,
    SerializationError,
)
from .manager import RedisManager
from .models import BaseResultModel
from .repository import BaseRepository

__all__ = [
    "RedisManager",
    "create_redis_client_dependencies",
    "BaseRepository",
    "BaseResultModel",
    "RepositoryError",
    "SerializationError",
    "DeserializationError",
    "NotFoundError",
    "ResultModelCreationError",
]
