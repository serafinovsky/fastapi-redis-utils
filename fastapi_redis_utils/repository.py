import logging
from collections.abc import AsyncIterator
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.exceptions import WatchError

from .exceptions import (
    AtomicUpdateError,
    DeserializationError,
    NotFoundError,
    RepositoryError,
    ResultModelCreationError,
    SerializationError,
    TransientRepositoryError,
)
from .manager import RedisManager
from .models import BaseResultModel
from .utils import achunked, aitake, chunked

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

    def _make_pattern(self, pattern: str) -> str:
        return f"{self.key_prefix}{pattern}"

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
        full_key = self._make_key(key)
        try:
            result_model = self._create_result_model(data, key)
            serialized_data = self._serialize(data)
        except RepositoryError as e:
            logger.error(f"Create failed for key {full_key}: {e}")
            if skip_raise:
                return None
            raise

        redis_client = self.redis_manager.get_client()
        ttl_to_use = ttl if ttl is not None else self.default_ttl
        try:
            await redis_client.set(full_key, serialized_data, ex=ttl_to_use)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return None
            raise TransientRepositoryError("Transient Redis error during create") from e
        logger.debug(f"Created record with key: {full_key}")
        return result_model

    async def get(self, key: str, *, skip_raise: bool = True) -> ResultSchemaType | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            data = await redis_client.get(full_key)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return None
            raise TransientRepositoryError("Transient Redis error during get") from e

        if data is None:
            if skip_raise:
                return None
            raise NotFoundError(f"Record not found for key: {full_key}")

        try:
            stored_model = self._deserialize(data, self.create_model)
            return self._create_result_model(stored_model, key)
        except RepositoryError as e:
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
        full_key = self._make_key(key)
        redis_client = self.redis_manager.get_client()
        async with redis_client.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(full_key)
                existing_data = await pipe.get(full_key)
                if existing_data is None:
                    if skip_raise:
                        return None
                    raise NotFoundError(f"Record not found for key: {full_key}")

                existing_model = self._deserialize(existing_data, self.create_model)
                updated_model = existing_model.model_copy(update=data.model_dump(exclude_unset=True))
                ttl_to_use = ttl if ttl is not None else self.default_ttl
                pipe.multi()
                pipe.set(full_key, self._serialize(updated_model), ex=ttl_to_use)
                await pipe.execute()
                logger.debug("Updated record with key: %s", full_key)
                return self._create_result_model(updated_model, key)
            except WatchError as e:
                if skip_raise:
                    return None
                raise AtomicUpdateError("Atomic update failed") from e
            except (RedisConnectionError, RedisTimeoutError) as e:
                if skip_raise:
                    return None
                raise TransientRepositoryError("Transient Redis error") from e
            except RepositoryError as e:
                logger.error("Failed to update data for key %s: %s", full_key, e)
                if skip_raise:
                    return None
                raise

    async def delete(self, key: str, *, skip_raise: bool = True) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            deleted: int = await redis_client.unlink(full_key)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return False
            raise TransientRepositoryError("Transient Redis error during delete") from e
        logger.debug(f"Deleted record with key: {full_key}")
        if deleted > 0:
            return True
        if skip_raise:
            return False
        raise NotFoundError(f"Record not found for key: {full_key}")

    async def exists(self, key: str) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            return bool(await redis_client.exists(full_key))
        except (RedisConnectionError, RedisTimeoutError) as e:
            raise TransientRepositoryError("Transient Redis error during exists") from e

    async def list(
        self,
        pattern: str = "*",
        limit: int | None = None,
        *,
        skip_raise: bool = True,
    ) -> list[ResultSchemaType]:
        result: list[ResultSchemaType] = []
        async for model in aitake(self._iter_models(pattern=pattern, skip_raise=skip_raise), limit):
            result.append(model)
        return result

    async def _iter_models(
        self,
        *,
        pattern: str = "*",
        skip_raise: bool = True,
        mget_chunk_size: int = 500,
    ) -> AsyncIterator[ResultSchemaType]:
        redis_client = self.redis_manager.get_client()
        full_pattern = self._make_pattern(pattern)

        buffer_keys: list[str] = []
        try:
            async for found_key in redis_client.scan_iter(match=full_pattern, count=1000):
                buffer_keys.append(found_key)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return
            raise TransientRepositoryError("Transient Redis error during list (scan_iter)") from e

        if not buffer_keys:
            return

        for chunk_keys in chunked(buffer_keys, mget_chunk_size):
            try:
                values = await redis_client.mget(chunk_keys)
            except (RedisConnectionError, RedisTimeoutError) as e:
                if skip_raise:
                    return
                raise TransientRepositoryError("Transient Redis error during list (mget)") from e

            for key, value in zip(chunk_keys, values, strict=False):
                if value is None:
                    continue
                try:
                    raw_key = key.removeprefix(self.key_prefix)
                    stored_model = self._deserialize(value, self.create_model)
                    yield self._create_result_model(stored_model, raw_key)
                except RepositoryError as e:
                    logger.warning(f"Failed to deserialize data for key {key}: {e}")
                    if not skip_raise:
                        raise
                    continue

    async def count(self, pattern: str = "*") -> int:
        redis_client = self.redis_manager.get_client()
        count = 0
        try:
            async for _ in redis_client.scan_iter(match=self._make_pattern(pattern), count=1000):
                count += 1
        except (RedisConnectionError, RedisTimeoutError) as e:
            raise TransientRepositoryError("Transient Redis error during count") from e
        return count

    async def set_ttl(self, key: str, ttl: int, *, skip_raise: bool = True) -> bool:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            result = await redis_client.expire(full_key, ttl)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return False
            raise TransientRepositoryError("Transient Redis error during set_ttl") from e
        if result:
            return True
        if skip_raise:
            return False
        raise NotFoundError(f"Record not found for key: {full_key}")

    async def get_ttl(self, key: str, *, skip_raise: bool = True) -> int | None:
        redis_client = self.redis_manager.get_client()
        full_key = self._make_key(key)
        try:
            ttl: int = await redis_client.ttl(full_key)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return None
            raise TransientRepositoryError("Transient Redis error during get_ttl") from e
        if ttl == -2:
            if skip_raise:
                return None
            raise NotFoundError(f"Record not found for key: {full_key}")
        return ttl

    async def clear(
        self,
        pattern: str = "*",
        *,
        skip_raise: bool = True,
        dry_run: bool = False,
        max_delete: int | None = None,
        batch_size: int = 500,
    ) -> int:
        redis_client = self.redis_manager.get_client()
        full_pattern = self._make_pattern(pattern)
        total_deleted = 0
        try:
            async for batch in achunked(redis_client.scan_iter(match=full_pattern, count=1000), batch_size):
                if max_delete is not None:
                    remaining = max_delete - total_deleted
                    if remaining >= 0:
                        batch = batch[:remaining]

                if dry_run:
                    total_deleted += len(batch)
                    continue

                if not batch:
                    break

                deleted = await redis_client.unlink(*batch)
                total_deleted += int(deleted)
        except (RedisConnectionError, RedisTimeoutError) as e:
            if skip_raise:
                return total_deleted
            raise TransientRepositoryError("Transient Redis error during clear") from e

        if total_deleted:
            logger.info(f"Cleared {total_deleted} records")

        if total_deleted == 0 and not skip_raise:
            raise NotFoundError(f"No records found for pattern: {full_pattern}")
        return total_deleted
