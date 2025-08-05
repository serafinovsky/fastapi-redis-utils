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
    """Create a mock Redis manager."""
    manager = MagicMock(spec=RedisManager)
    manager.get_client = AsyncMock()
    return manager


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = AsyncMock()
    return client


@pytest.fixture
def repository(mock_redis_manager, mock_redis_client):
    """Create a repository instance with mocked dependencies."""
    mock_redis_manager.get_client.return_value = mock_redis_client
    return BaseRepository[UserCreate, UserUpdate, UserResult](
        redis_manager=mock_redis_manager,
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
    async def test_create(self, repository, mock_redis_client):
        """Test record creation."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        result = await repository.create("test_key", user)

        assert result.username == user.username
        assert result.email == user.email
        assert result.full_name == user.full_name
        assert result.age == user.age
        assert result.is_active == user.is_active
        assert result.id == "test_key"
        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][0] == "user:test_key"
        assert call_args[0][1] == 3600  # default_ttl

    @pytest.mark.asyncio
    async def test_create_with_custom_ttl(self, repository, mock_redis_client):
        """Test record creation with custom TTL."""
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        await repository.create("test_key", user, ttl=7200)

        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][1] == 7200

    @pytest.mark.asyncio
    async def test_create_without_ttl(self, repository, mock_redis_client):
        """Test record creation without TTL."""
        repository.default_ttl = None
        user = UserCreate(username="test", email="test@example.com", full_name="Test User", age=25)

        await repository.create("test_key", user)

        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_existing(self, repository, mock_redis_client):
        """Test getting existing record."""
        user_data = (
            '{"username": "test", "email": "test@example.com", "full_name": "Test User", "age": 25, "is_active": true}'
        )
        mock_redis_client.get.return_value = user_data

        result = await repository.get("test_key")

        assert result is not None
        assert isinstance(result, UserCreate)
        assert result.username == "test"
        assert result.email == "test@example.com"
        assert result.full_name == "Test User"
        assert result.age == 25
        assert result.is_active is True
        assert result.id == "test_key"
        mock_redis_client.get.assert_called_once_with("user:test_key")

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, repository, mock_redis_client):
        """Test getting non-existent record."""
        mock_redis_client.get.return_value = None

        result = await repository.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing(self, repository, mock_redis_client):
        """Test updating existing record with partial update."""
        existing_data = (
            '{"username": "old", "email": "old@example.com", "full_name": "Old User", "age": 30, "is_active": true}'
        )
        mock_redis_client.get.return_value = existing_data

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

        mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, repository, mock_redis_client):
        """Test updating non-existent record."""
        mock_redis_client.get.return_value = None

        update_data = UserUpdate(email="new@example.com")
        result = await repository.update("test_key", update_data)

        assert result is None
        mock_redis_client.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_existing(self, repository, mock_redis_client):
        """Test deleting existing record."""
        mock_redis_client.delete.return_value = 1

        result = await repository.delete("test_key")

        assert result is True
        mock_redis_client.delete.assert_called_once_with("user:test_key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, repository, mock_redis_client):
        """Test deleting non-existent record."""
        mock_redis_client.delete.return_value = 0

        result = await repository.delete("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, repository, mock_redis_client):
        """Test checking existence of existing record."""
        mock_redis_client.exists.return_value = 1

        result = await repository.exists("test_key")

        assert result is True
        mock_redis_client.exists.assert_called_once_with("user:test_key")

    @pytest.mark.asyncio
    async def test_exists_false(self, repository, mock_redis_client):
        """Test checking existence of non-existent record."""
        mock_redis_client.exists.return_value = 0

        result = await repository.exists("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_list(self, repository, mock_redis_client):
        """Test listing records."""
        mock_redis_client.keys.return_value = [b"user:key1", b"user:key2"]

        mock_pipeline = AsyncMock()
        mock_pipeline.get = AsyncMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[
                '{"username": "user1", "email": "user1@example.com", "full_name": "User 1", "age": 25, "is_active": true}',
                '{"username": "user2", "email": "user2@example.com", "full_name": "User 2", "age": 30, "is_active": false}',
            ]
        )
        mock_redis_client.pipeline = AsyncMock(return_value=mock_pipeline)

        result = await repository.list()

        assert len(result) == 2
        assert all(isinstance(user, UserCreate) for user in result)
        assert result[0].id == "user:key1"
        assert result[1].id == "user:key2"
        assert result[0].username == "user1"
        assert result[1].username == "user2"

    @pytest.mark.asyncio
    async def test_list_with_limit(self, repository, mock_redis_client):
        """Test listing records with limit."""
        mock_redis_client.keys.return_value = [b"user:key1", b"user:key2", b"user:key3"]

        mock_pipeline = AsyncMock()
        mock_pipeline.get = AsyncMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[
                '{"username": "user1", "email": "user1@example.com", "full_name": "User 1", "age": 25, "is_active": true}',
                '{"username": "user2", "email": "user2@example.com", "full_name": "User 2", "age": 30, "is_active": false}',
            ]
        )
        mock_redis_client.pipeline = AsyncMock(return_value=mock_pipeline)

        result = await repository.list(limit=2)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_count(self, repository, mock_redis_client):
        """Test counting records."""
        mock_redis_client.keys.return_value = [b"user:key1", b"user:key2", b"user:key3"]

        result = await repository.count()

        assert result == 3

    @pytest.mark.asyncio
    async def test_set_ttl(self, repository, mock_redis_client):
        """Test setting TTL."""
        mock_redis_client.expire.return_value = 1

        result = await repository.set_ttl("test_key", 7200)

        assert result is True
        mock_redis_client.expire.assert_called_once_with("user:test_key", 7200)

    @pytest.mark.asyncio
    async def test_get_ttl(self, repository, mock_redis_client):
        """Test getting TTL."""
        mock_redis_client.ttl.return_value = 3600

        result = await repository.get_ttl("test_key")

        assert result == 3600
        mock_redis_client.ttl.assert_called_once_with("user:test_key")

    @pytest.mark.asyncio
    async def test_get_ttl_nonexistent(self, repository, mock_redis_client):
        """Test getting TTL for non-existent key."""
        mock_redis_client.ttl.return_value = -2

        result = await repository.get_ttl("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, repository, mock_redis_client):
        """Test clearing records."""
        mock_redis_client.keys.return_value = [b"user:key1", b"user:key2"]
        mock_redis_client.delete.return_value = 2

        result = await repository.clear()

        assert result == 2
        mock_redis_client.delete.assert_called_once_with(b"user:key1", b"user:key2")
