from unittest.mock import AsyncMock, patch

import pytest

from fastapi_redis_utils import create_redis_client_dependencies


class TestDependency:
    """Tests for FastAPI dependencies."""

    @pytest.fixture
    def mock_redis_client(self):
        """Fixture for mocking Redis client."""
        return AsyncMock()

    def test_create_redis_client_dependencies(self, redis_manager):
        """Test dependency creation."""
        dependency = create_redis_client_dependencies(redis_manager)
        assert callable(dependency)
        assert dependency.__name__ == "get_redis_client"

    @pytest.mark.asyncio
    async def test_dependency_success(self, redis_manager, mock_redis_client):
        """Test successful dependency execution."""
        redis_manager.get_client = lambda: mock_redis_client

        dependency = create_redis_client_dependencies(redis_manager)

        with patch.object(redis_manager, "ensure_connection") as mock_ensure:
            result = await dependency()

            mock_ensure.assert_called_once()
            assert result == mock_redis_client

    @pytest.mark.asyncio
    async def test_dependency_ensure_connection_called(self, redis_manager, mock_redis_client):
        """Test that ensure_connection is called."""
        redis_manager.get_client = lambda: mock_redis_client

        dependency = create_redis_client_dependencies(redis_manager)

        with patch.object(redis_manager, "ensure_connection") as mock_ensure:
            await dependency()

            mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_dependency_get_client_called(self, redis_manager, mock_redis_client):
        """Test that get_client is called."""
        redis_manager.get_client = lambda: mock_redis_client

        dependency = create_redis_client_dependencies(redis_manager)

        with patch.object(redis_manager, "ensure_connection"):
            result = await dependency()

            assert result == mock_redis_client

    @pytest.mark.asyncio
    async def test_dependency_with_connection_error(self, redis_manager):
        """Test dependency with connection error."""
        redis_manager.ensure_connection = AsyncMock(side_effect=Exception("Connection failed"))

        dependency = create_redis_client_dependencies(redis_manager)

        with pytest.raises(Exception, match="Connection failed"):
            await dependency()

    @pytest.mark.asyncio
    async def test_dependency_with_client_error(self, redis_manager):
        """Test dependency with client error."""
        redis_manager.get_client = lambda: (_ for _ in ()).throw(RuntimeError("Client error"))

        dependency = create_redis_client_dependencies(redis_manager)

        with patch.object(redis_manager, "ensure_connection"):
            with pytest.raises(RuntimeError, match="Client error"):
                await dependency()
