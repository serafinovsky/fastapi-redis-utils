"""
Tests for BaseRepository.

This module contains tests for the BaseRepository class that provides
CRUD operations for Pydantic models with Redis.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from fastapi_redis_utils import BaseRepository, BaseResultModel, RedisManager


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
    id: str | None = None

    def set_id(self, id: str) -> None:
        self.id = id


@pytest.fixture
def mock_redis_manager():
    """Create a mock Redis manager for initialization tests."""
    manager = MagicMock(spec=RedisManager)
    manager.get_client = AsyncMock()
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
        with pytest.raises(ValueError, match="Failed to deserialize model"):
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
        assert result.id == "test_key"

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
        assert result.id == "test_key"

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
        assert result.id == "test_key"

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
