import logging
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .manager import RedisManager
from .models import BaseResultModel

logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
ResultSchemaType = TypeVar("ResultSchemaType", bound=BaseResultModel)


class BaseRepository(Generic[CreateSchemaType, UpdateSchemaType, ResultSchemaType]):
    def __init__(
        self,
        redis_manager: RedisManager,
        create_model: type[CreateSchemaType],
        update_model: type[UpdateSchemaType],
        result_model: type[ResultSchemaType],
        key_prefix: str | None = None,
        default_ttl: int | None = None,
    ):
        self.redis_manager = redis_manager
        self.create_model = create_model
        self.update_model = update_model
        self.result_model = result_model
        self.key_prefix = key_prefix or f"{self.create_model.__name__.lower()}:"
        self.default_ttl = default_ttl

    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    def _serialize(self, data: T) -> str:
        try:
            return data.model_dump_json()
        except Exception as e:
            logger.error(f"Failed to serialize model: {e}")
            raise ValueError("Failed to serialize model") from e

    def _deserialize(self, data: str, model: type[T]) -> T:
        try:
            return model.model_validate_json(data)
        except ValidationError as e:
            logger.error(f"Failed to deserialize model: {e}")
            raise ValueError("Failed to deserialize model") from e
        except Exception as e:
            logger.error(f"Unexpected error deserializing model: {e}")
            raise ValueError("Failed to deserialize model") from e

    def _create_result_model(self, data: CreateSchemaType, key: str) -> ResultSchemaType:
        result_model = self.result_model(**data.model_dump())
        result_model.set_id(key)
        return result_model

    async def create(self, key: str, data: CreateSchemaType, ttl: int | None = None) -> ResultSchemaType:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        serialized_data = self._serialize(data)
        ttl_to_use = ttl if ttl is not None else self.default_ttl
        if ttl_to_use is not None:
            await redis_client.setex(full_key, ttl_to_use, serialized_data)
        else:
            await redis_client.set(full_key, serialized_data)
        logger.debug(f"Created record with key: {full_key}")
        return self._create_result_model(data, key)

    async def get(self, key: str) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        data = await redis_client.get(full_key)
        if data is None:
            return None

        try:
            stored_model = self._deserialize(data, self.create_model)
            return self._create_result_model(stored_model, key)
        except ValueError as e:
            logger.error(f"Failed to deserialize data for key {full_key}: {e}")
            return None

    async def update(
        self,
        key: str,
        data: UpdateSchemaType,
        ttl: int | None = None,
    ) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        existing_data = await redis_client.get(full_key)
        if existing_data is None:
            return None

        try:
            existing_model = self._deserialize(existing_data, self.create_model)
            update_dict = data.model_dump(exclude_unset=True)
            updated_dict = existing_model.model_dump()
            updated_dict.update(update_dict)
            updated_model = self.create_model(**updated_dict)
            serialized_data = self._serialize(updated_model)
            ttl_to_use = ttl if ttl is not None else self.default_ttl
            if ttl_to_use is not None:
                await redis_client.setex(full_key, ttl_to_use, serialized_data)
            else:
                await redis_client.set(full_key, serialized_data)
            logger.debug(f"Updated record with key: {full_key}")
            return self._create_result_model(updated_model, key)
        except ValueError as e:
            logger.error(f"Failed to update data for key {full_key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        deleted: int = await redis_client.delete(full_key)
        logger.debug(f"Deleted record with key: {full_key}")
        return deleted > 0

    async def exists(self, key: str) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        return bool(await redis_client.exists(full_key))

    async def list(self, pattern: str = "*", limit: int | None = None) -> list[ResultSchemaType]:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        keys = await redis_client.keys(full_pattern)
        if limit:
            keys = keys[:limit]

        if not keys:
            return []

        pipeline = await redis_client.pipeline()
        for key in keys:
            await pipeline.get(key)
        values = await pipeline.execute()
        result = []
        for key, value in zip(keys, values, strict=False):
            if value is not None:
                try:
                    clean_key = key.decode() if isinstance(key, bytes) else key
                    stored_model = self._deserialize(value, self.create_model)
                    model_instance = self._create_result_model(stored_model, clean_key)
                    result.append(model_instance)
                except ValueError as e:
                    logger.warning(f"Failed to deserialize data for key {clean_key}: {e}")
                    continue
        return result

    async def count(self, pattern: str = "*") -> int:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        keys = await redis_client.keys(full_pattern)
        return len(keys)

    async def set_ttl(self, key: str, ttl: int) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        return bool(await redis_client.expire(full_key, ttl))

    async def get_ttl(self, key: str) -> int | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        ttl = await redis_client.ttl(full_key)
        return ttl if ttl != -2 else None

    async def clear(self, pattern: str = "*") -> int:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        keys = await redis_client.keys(full_pattern)
        if not keys:
            return 0
        deleted: int = await redis_client.delete(*keys)
        logger.info(f"Cleared {deleted} records")
        return deleted
