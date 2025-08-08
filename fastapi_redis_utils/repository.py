import logging
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .exceptions import (
    DeserializationError,
    NotFoundError,
    RepositoryError,
    ResultModelCreationError,
    SerializationError,
)
from .manager import RedisManager
from .models import BaseResultModel
from .utils import achunked, chunked

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
            raise SerializationError("Failed to serialize model") from e

    def _deserialize(self, data: str, model: type[T]) -> T:
        try:
            return model.model_validate_json(data)
        except ValidationError as e:
            logger.error(f"Failed to deserialize model: {e}")
            raise DeserializationError("Failed to deserialize model") from e
        except Exception as e:
            logger.error(f"Unexpected error deserializing model: {e}")
            raise DeserializationError("Unexpected error deserializing model") from e

    def _create_result_model(self, data: CreateSchemaType, key: str) -> ResultSchemaType:
        try:
            result_model = self.result_model(**data.model_dump())
            result_model.set_key(key)
            return result_model
        except ValidationError as e:
            logger.error(f"Failed to create result model for key {key}: {e}")
            raise ResultModelCreationError("Failed to create result model") from e

    async def create(
        self,
        key: str,
        data: CreateSchemaType,
        ttl: int | None = None,
        *,
        skip_raise: bool = True,
    ) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            result_model = self._create_result_model(data, key)
            serialized_data = self._serialize(data)
        except (ResultModelCreationError, SerializationError) as e:
            logger.error(f"Create failed for key {full_key}: {e}")
            if skip_raise:
                return None
            raise
        ttl_to_use = ttl if ttl is not None else self.default_ttl
        if ttl_to_use is not None:
            await redis_client.setex(full_key, ttl_to_use, serialized_data)
        else:
            await redis_client.set(full_key, serialized_data)
        logger.debug(f"Created record with key: {full_key}")
        return result_model

    async def get(self, key: str, *, skip_raise: bool = True) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        data = await redis_client.get(full_key)
        if data is None:
            if skip_raise:
                return None
            raise NotFoundError(f"Record not found for key: {full_key}")

        try:
            stored_model = self._deserialize(data, self.create_model)
            return self._create_result_model(stored_model, key)
        except DeserializationError as e:
            logger.error(f"Failed to deserialize data for key {full_key}: {e}")
            if skip_raise:
                return None
            raise

    async def update(
        self,
        key: str,
        data: UpdateSchemaType,
        ttl: int | None = None,
        *,
        skip_raise: bool = True,
    ) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        existing_data = await redis_client.get(full_key)
        if existing_data is None:
            if skip_raise:
                return None
            raise NotFoundError(f"Record not found for key: {full_key}")

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
        except RepositoryError as e:
            logger.error(f"Failed to update data for key {full_key}: {e}")
            if skip_raise:
                return None
            raise

    async def delete(self, key: str, *, skip_raise: bool = True) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        deleted: int = await redis_client.delete(full_key)
        logger.debug(f"Deleted record with key: {full_key}")
        if deleted > 0:
            return True
        if skip_raise:
            return False
        raise NotFoundError(f"Record not found for key: {full_key}")

    async def exists(self, key: str) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        return bool(await redis_client.exists(full_key))

    async def list(
        self,
        pattern: str = "*",
        limit: int | None = None,
        *,
        skip_raise: bool = True,
    ) -> list[ResultSchemaType]:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        collected_keys: list[str] = []
        async for found_key in redis_client.scan_iter(match=full_pattern, count=1000):
            collected_keys.append(found_key)
            if limit is not None and len(collected_keys) >= limit:
                break

        if not collected_keys:
            return []

        result: list[ResultSchemaType] = []
        mget_chunk_size = 500
        for chunk_keys in chunked(collected_keys, mget_chunk_size):
            values = await redis_client.mget(chunk_keys)
            for key, value in zip(chunk_keys, values, strict=False):
                if value is None:
                    continue

                try:
                    raw_key = key.removeprefix(self.key_prefix)
                    stored_model = self._deserialize(value, self.create_model)
                    model_instance = self._create_result_model(stored_model, raw_key)
                    result.append(model_instance)
                except RepositoryError as e:
                    logger.warning(f"Failed to deserialize data for key {key}: {e}")
                    if skip_raise:
                        continue
                    raise
        return result

    async def count(self, pattern: str = "*") -> int:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        count = 0
        async for _ in redis_client.scan_iter(match=full_pattern, count=2000):
            count += 1
        return count

    async def set_ttl(self, key: str, ttl: int, *, skip_raise: bool = True) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        result = await redis_client.expire(full_key, ttl)
        if result:
            return True
        if skip_raise:
            return False
        raise NotFoundError(f"Record not found for key: {full_key}")

    async def get_ttl(self, key: str, *, skip_raise: bool = True) -> int | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        ttl: int = await redis_client.ttl(full_key)
        if ttl == -2:
            if skip_raise:
                return None
            raise NotFoundError(f"Record not found for key: {full_key}")
        return ttl

    async def clear(self, pattern: str = "*", *, skip_raise: bool = True) -> int:
        redis_client = self.redis_manager.get_client()
        full_pattern = f"{self.key_prefix}{pattern}"
        batch_size = 500
        total_deleted = 0
        async for batch in achunked(redis_client.scan_iter(match=full_pattern, count=2000), batch_size):
            try:
                deleted = await redis_client.unlink(*batch)
            except Exception:
                deleted = await redis_client.delete(*batch)
            total_deleted += int(deleted)

        if total_deleted:
            logger.info(f"Cleared {total_deleted} records")
        if total_deleted == 0 and not skip_raise:
            raise NotFoundError(f"No records found for pattern: {full_pattern}")
        return total_deleted
