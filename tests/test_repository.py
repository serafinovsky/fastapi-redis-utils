"""
Tests for BaseRepository.

This module contains tests for the BaseRepository class that provides
CRUD operations for Pydantic models with Redis.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from fastapi_redis_utils import (
    BaseRepository,
    BaseResultModel,
    DeserializationError,
    NotFoundError,
    RedisManager,
    RepositoryError,
    SerializationError,
)


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    age: int
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    full_name: str | None = None
    age: int | None = None
    is_active: bool | None = None


class UserResult(UserCreate, BaseResultModel):
    key: str | None = None

    def set_key(self, key: str) -> None:
        self.key = key


@pytest.fixture
def mock_redis_manager():
    """Create a mock Redis manager for initialization tests."""
    manager = MagicMock(spec=RedisManager)
    manager.get_client = MagicMock()
    return manager


@pytest.fixture
async def repository(connected_redis_manager):
    """Create a repository instance with fake Redis."""
    return BaseRepository[UserCreate, UserUpdate, UserResult](
        redis_manager=connected_redis_manager,
        create_model=UserCreate,
        update_model=UserUpdate,
        result_model=UserResult,
        key_prefix="user:",
        default_ttl=3600,
    )


class TestBaseRepository:
    """Test BaseRepository functionality."""

    def test_init(self, mock_redis_manager):
        """Test repository initialization."""
        repo = BaseRepository[UserCreate, UserUpdate, UserResult](
            redis_manager=mock_redis_manager,
            create_model=UserCreate,
            update_model=UserUpdate,
            result_model=UserResult,
            key_prefix="test:",
            default_ttl=7200,
        )

        assert repo.redis_manager == mock_redis_manager
        assert repo.create_model == UserCreate
        assert repo.update_model == UserUpdate
        assert repo.result_model == UserResult
        assert repo.key_prefix == "test:"
        assert repo.default_ttl == 7200

    def test_init_default_key_prefix(self, mock_redis_manager):
        """Test repository initialization with default key prefix."""
        repo = BaseRepository[UserCreate, UserUpdate, UserResult](
            redis_manager=mock_redis_manager,
            create_model=UserCreate,
            update_model=UserUpdate,
            result_model=UserResult,
        )

        assert repo.key_prefix == "usercreate:"

    def test_make_key(self, repository):
        """Test key generation."""
        key = repository._make_key("test_key")
        assert key == "user:test_key"

    def test_serialize(self, repository):
        """Test model serialization."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        serialized = repository._serialize(user)
        assert isinstance(serialized, str)
        assert "test" in serialized
        assert "test@example.com" in serialized

    def test_deserialize(self, repository):
        """Test model deserialization."""
        user_data = (
            '{"username": "test", "email": "test@example.com", "full_name": "Test User", "age": 25, "is_active": true}'
        )

        user = repository._deserialize(user_data, UserCreate)
        assert isinstance(user, UserCreate)
        assert user.username == "test"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.age == 25
        assert user.is_active is True

    def test_deserialize_invalid_json(self, repository):
        """Test deserialization with invalid JSON."""
        with pytest.raises(DeserializationError, match="Failed to deserialize model"):
            repository._deserialize("invalid json", UserCreate)

    @pytest.mark.asyncio
    async def test_create(self, repository):
        """Test record creation."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        result = await repository.create("test_key", user)

        assert result.username == user.username
        assert result.email == user.email
        assert result.full_name == user.full_name
        assert result.age == user.age
        assert result.is_active == user.is_active
        assert result.key == "test_key"

        stored_user = await repository.get("test_key")
        assert stored_user is not None
        assert stored_user.username == user.username

    @pytest.mark.asyncio
    async def test_create_with_custom_ttl(self, repository: BaseRepository[UserCreate, UserUpdate, UserResult]):
        """Test record creation with custom TTL."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        assert await repository.get("test_key") is None
        await repository.create("test_key", user, ttl=7200)

        stored_user = await repository.get("test_key")
        assert stored_user is not None
        ttl = await repository.get_ttl("test_key")
        assert ttl is not None
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_create_without_ttl(self, repository):
        """Test record creation without TTL."""
        repository.default_ttl = None
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        await repository.create("test_key", user)

        stored_user = await repository.get("test_key")
        assert stored_user is not None
        ttl = await repository.get_ttl("test_key")
        assert ttl == -1  # No TTL set

    @pytest.mark.asyncio
    async def test_get_existing(self, repository):
        """Test getting existing record."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)

        result = await repository.get("test_key")

        assert result is not None
        assert isinstance(result, UserCreate)
        assert result.username == "test"
        assert result.email == "test@example.com"
        assert result.full_name == "Test User"
        assert result.age == 25
        assert result.is_active is True
        assert result.key == "test_key"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repository):
        """Test getting non-existent record."""
        result = await repository.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_deserialization_error(self, repository):
        """Test getting record with deserialization error - should return None."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)

        # Manually corrupt the data in Redis to simulate deserialization error
        redis_client = repository.redis_manager.get_client()
        full_key = repository._make_key("test_key")
        await redis_client.set(full_key, "invalid json data")

        result = await repository.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing(self, repository):
        """Test updating existing record with partial update."""
        user = UserCreate(username="old", email="old@example.com", full_name="Old User", age=30)
        await repository.create("test_key", user)

        update_data = UserUpdate(email="new@example.com", age=31)

        result = await repository.update("test_key", update_data)

        assert result is not None
        assert isinstance(result, UserCreate)
        assert result.username == "old"
        assert result.email == "new@example.com"
        assert result.full_name == "Old User"
        assert result.age == 31
        assert result.is_active is True
        assert result.key == "test_key"

        stored_user = await repository.get("test_key")
        assert stored_user.email == "new@example.com"
        assert stored_user.age == 31

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, repository):
        """Test updating non-existent record."""
        update_data = UserUpdate(email="new@example.com")
        result = await repository.update("test_key", update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self, repository):
        """Test deleting existing record."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)

        result = await repository.delete("test_key")

        assert result is True

        stored_user = await repository.get("test_key")
        assert stored_user is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, repository):
        """Test deleting non-existent record."""
        result = await repository.delete("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, repository):
        """Test checking existence of existing record."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)

        result = await repository.exists("test_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, repository):
        """Test checking existence of non-existent record."""
        result = await repository.exists("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_list(self, repository):
        """Test listing records."""
        user1 = UserCreate(username="user1", email="user1@example.com", full_name="User 1", age=25)
        user2 = UserCreate(username="user2", email="user2@example.com", full_name="User 2", age=30, is_active=False)

        await repository.create("key1", user1)
        await repository.create("key2", user2)

        result = await repository.list()

        assert len(result) == 2
        assert all(isinstance(user, UserCreate) for user in result)
        usernames = [user.username for user in result]
        assert "user1" in usernames
        assert "user2" in usernames

    @pytest.mark.asyncio
    async def test_list_with_limit(self, repository):
        """Test listing records with limit."""
        user1 = UserCreate(username="user1", email="user1@example.com", full_name="User 1", age=25)
        user2 = UserCreate(username="user2", email="user2@example.com", full_name="User 2", age=30)
        user3 = UserCreate(username="user3", email="user3@example.com", full_name="User 3", age=35)

        await repository.create("key1", user1)
        await repository.create("key2", user2)
        await repository.create("key3", user3)

        result = await repository.list(limit=2)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self, repository):
        """Test listing records when no records exist - should return empty list."""
        result = await repository.list()

        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_with_deserialization_errors(self, repository):
        """Test listing records with some deserialization errors - should skip corrupted records."""
        user1 = UserCreate(username="user1", email="user1@example.com", full_name="User 1", age=25)
        user2 = UserCreate(username="user2", email="user2@example.com", full_name="User 2", age=30)
        user3 = UserCreate(username="user3", email="user3@example.com", full_name="User 3", age=35)

        await repository.create("key1", user1)
        await repository.create("key2", user2)
        await repository.create("key3", user3)

        # Corrupt one of the records to simulate deserialization error
        redis_client = repository.redis_manager.get_client()
        full_key = repository._make_key("key2")
        await redis_client.set(full_key, "invalid json data")

        result = await repository.list()

        # Should return only valid records, skipping the corrupted one
        assert len(result) == 2
        usernames = [user.username for user in result]
        assert "user1" in usernames
        assert "user3" in usernames
        assert "user2" not in usernames  # Corrupted record should be skipped

    @pytest.mark.asyncio
    async def test_count(self, repository):
        """Test counting records."""
        user1 = UserCreate(username="user1", email="user1@example.com", full_name="User 1", age=25)
        user2 = UserCreate(username="user2", email="user2@example.com", full_name="User 2", age=30)
        user3 = UserCreate(username="user3", email="user3@example.com", full_name="User 3", age=35)

        await repository.create("key1", user1)
        await repository.create("key2", user2)
        await repository.create("key3", user3)

        result = await repository.count()

        assert result == 3

    @pytest.mark.asyncio
    async def test_set_ttl(self, repository):
        """Test setting TTL."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)

        result = await repository.set_ttl("test_key", 7200)

        assert result is True

        ttl = await repository.get_ttl("test_key")
        assert ttl is not None
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_get_ttl(self, repository):
        """Test getting TTL."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user, ttl=3600)

        result = await repository.get_ttl("test_key")

        assert result is not None
        assert result > 0

    @pytest.mark.asyncio
    async def test_get_ttl_nonexistent(self, repository):
        """Test getting TTL for non-existent key."""
        result = await repository.get_ttl("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, repository):
        """Test clearing records."""
        user1 = UserCreate(username="user1", email="user1@example.com", full_name="User 1", age=25)
        user2 = UserCreate(username="user2", email="user2@example.com", full_name="User 2", age=30)

        await repository.create("key1", user1)
        await repository.create("key2", user2)

        result = await repository.clear()

        assert result == 2

        count = await repository.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_with_deserialization_error_raise(self, repository):
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)
        await repository.create("test_key", user)
        redis_client = repository.redis_manager.get_client()
        full_key = repository._make_key("test_key")
        await redis_client.set(full_key, "invalid json data")

        with pytest.raises(DeserializationError):
            await repository.get("test_key", skip_raise=False)

    @pytest.mark.asyncio
    async def test_get_nonexistent_raise(self, repository):
        with pytest.raises(NotFoundError):
            await repository.get("missing", skip_raise=False)

    @pytest.mark.asyncio
    async def test_update_nonexistent_raise(self, repository):
        update_data = UserUpdate(email="new@example.com")
        with pytest.raises(NotFoundError):
            await repository.update("test_key", update_data, skip_raise=False)

    @pytest.mark.asyncio
    async def test_update_serialization_error_skip_and_raise(self, repository):
        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        await repository.create("k1", user)
        update_data = UserUpdate(email="x@x")

        with patch.object(type(repository), "_serialize", side_effect=SerializationError("boom")):
            assert await repository.update("k1", update_data) is None
            with pytest.raises(SerializationError):
                await repository.update("k1", update_data, skip_raise=False)

    @pytest.mark.asyncio
    async def test_list_with_deserialization_error_raise(self, repository):
        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        await repository.create("k", user)
        redis_client = repository.redis_manager.get_client()
        await redis_client.set(repository._make_key("k"), "invalid json data")
        with pytest.raises(DeserializationError):
            await repository.list(skip_raise=False)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raise(self, repository):
        with pytest.raises(NotFoundError):
            await repository.delete("missing", skip_raise=False)

    @pytest.mark.asyncio
    async def test_set_ttl_nonexistent_skip_and_raise(self, repository):
        assert await repository.set_ttl("missing", 1) is False
        with pytest.raises(NotFoundError):
            await repository.set_ttl("missing", 1, skip_raise=False)

    @pytest.mark.asyncio
    async def test_get_ttl_nonexistent_raise(self, repository):
        with pytest.raises(NotFoundError):
            await repository.get_ttl("missing", skip_raise=False)

    @pytest.mark.asyncio
    async def test_clear_empty_raise(self, repository):
        with pytest.raises(NotFoundError):
            await repository.clear("nope:*", skip_raise=False)

    def test_serialize_error(self, repository):
        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        with patch.object(UserCreate, "model_dump_json", side_effect=Exception("boom")):
            with pytest.raises(SerializationError):
                repository._serialize(user)

    def test_deserialize_unexpected_error(self, repository):
        with patch.object(UserCreate, "model_validate_json", side_effect=Exception("boom")):
            with pytest.raises(RepositoryError):
                repository._deserialize("{}", UserCreate)

    @pytest.mark.asyncio
    async def test_create_result_model_error(self, connected_redis_manager) -> None:
        class BadResult(BaseResultModel, BaseModel):
            required_extra: int

            def set_key(self, key: str) -> None:
                self.key = key

        repo = BaseRepository[UserCreate, UserUpdate, BadResult](
            redis_manager=connected_redis_manager,
            create_model=UserCreate,
            update_model=UserUpdate,
            result_model=BadResult,
            key_prefix="bad:",
        )

        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        with pytest.raises(RepositoryError):
            await repo.create("k", user, skip_raise=False)

    @pytest.mark.asyncio
    async def test_create_result_model_error_skip(self, connected_redis_manager) -> None:
        class BadResult(BaseResultModel, BaseModel):
            required_extra: int

            def set_key(self, key: str) -> None:
                self.key = key

        repo = BaseRepository[UserCreate, UserUpdate, BadResult](
            redis_manager=connected_redis_manager,
            create_model=UserCreate,
            update_model=UserUpdate,
            result_model=BadResult,
            key_prefix="bad:",
        )

        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        assert await repo.create("k", user) is None

    @pytest.mark.asyncio
    async def test_create_serialization_error_skip_and_raise(self, repository):
        user = UserCreate(username="u", email="e@e", full_name="F", age=1)
        with patch.object(UserCreate, "model_dump_json", side_effect=Exception("boom")):
            # skip_raise=True -> None
            assert await repository.create("k2", user) is None
            # skip_raise=False -> raise
            with pytest.raises(SerializationError):
                await repository.create("k3", user, skip_raise=False)

    @pytest.mark.asyncio
    async def test_update_without_ttl_else_branch(self, repository):
        repository.default_ttl = None
        user = UserCreate(username="u1", email="e1@example.com", full_name="U1", age=20)
        await repository.create("upd_no_ttl", user)
        update_data = UserUpdate(full_name="U1 Updated")
        result = await repository.update("upd_no_ttl", update_data)
        assert result is not None
        stored_user = await repository.get("upd_no_ttl")
        assert stored_user is not None
        assert stored_user.full_name == "U1 Updated"

    @pytest.mark.asyncio
    async def test_list_skips_none_values_from_mget(self, repository):
        user1 = UserCreate(username="a", email="a@e", full_name="A", age=1)
        user2 = UserCreate(username="b", email="b@e", full_name="B", age=2)
        await repository.create("l1", user1)
        await repository.create("l2", user2)

        client = repository.redis_manager.get_client()
        original_mget = client.mget

        async def fake_mget(keys):
            values = await original_mget(keys)
            if values:
                values[0] = None
            return values

        with patch.object(client, "mget", side_effect=fake_mget):
            items = await repository.list()
            assert len(items) == 1

    @pytest.mark.asyncio
    async def test_clear_unlink_fallback_to_delete(self, repository):
        user1 = UserCreate(username="x", email="x@e", full_name="X", age=3)
        user2 = UserCreate(username="y", email="y@e", full_name="Y", age=4)
        await repository.create("c1", user1)
        await repository.create("c2", user2)

        client = repository.redis_manager.get_client()

        async def fake_unlink(*_args, **_kwargs):
            raise Exception("unlink not supported")

        with patch.object(client, "unlink", side_effect=fake_unlink):
            deleted = await repository.clear()
            assert deleted == 2
