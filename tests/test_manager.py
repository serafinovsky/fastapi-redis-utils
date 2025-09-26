from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as redis


class TestRedisManager:
    """Tests for RedisManager."""

    @pytest.fixture
    def mock_redis_client(self):
        """Fixture for mocking Redis client."""
        mock_client = AsyncMock(spec=redis.Redis)
        mock_client.ping = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_connection_pool(self):
        """Fixture for mocking connection pool."""
        return MagicMock(spec=redis.ConnectionPool)

    def test_init(self, redis_manager, get_redis_url):
        """Test RedisManager initialization."""
        assert redis_manager.dsn == get_redis_url
        assert redis_manager.max_connections == 10
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_connect_success(self, redis_manager, mock_redis_client, mock_connection_pool):
        """Test successful connection."""
        with (
            patch(
                "redis.asyncio.ConnectionPool.from_url",
                return_value=mock_connection_pool,
            ),
            patch("redis.asyncio.Redis", return_value=mock_redis_client),
        ):
            await redis_manager.connect()
            assert redis_manager.redis_client == mock_redis_client
            assert redis_manager._connection_pool == mock_connection_pool
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, redis_manager):
        """Test failed connection."""
        with patch("redis.asyncio.ConnectionPool.from_url", side_effect=Exception("Connection failed")):
            with pytest.raises(ConnectionError, match="Failed to connect to Redis"):
                await redis_manager.connect()

    @pytest.mark.asyncio
    async def test_connect_skips_when_already_initialized(self, redis_manager, mock_redis_client):
        """Test that connect() returns early if client is already set."""
        redis_manager.redis_client = mock_redis_client

        with (
            patch("redis.asyncio.ConnectionPool.from_url") as mock_from_url,
            patch("redis.asyncio.Redis") as mock_redis_ctor,
        ):
            await redis_manager.connect()

            mock_from_url.assert_not_called()
            mock_redis_ctor.assert_not_called()

    @pytest.mark.asyncio
    async def test_close(self, redis_manager, mock_redis_client):
        """Test connection closing."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._connection_pool = MagicMock()

        await redis_manager.close()

        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_close_with_exception(self, redis_manager, mock_redis_client):
        """Test connection closing with exception."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._connection_pool = MagicMock()

        # Simulate exception during close
        mock_redis_client.aclose.side_effect = Exception("Close error")

        await redis_manager.close()

        # Should still reset the state even if close fails
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_close_with_pool_exception(self, redis_manager, mock_redis_client):
        """Test connection closing with pool exception."""
        redis_manager.redis_client = mock_redis_client
        mock_pool = MagicMock()
        mock_pool.disconnect.side_effect = Exception("Pool disconnect error")
        redis_manager._connection_pool = mock_pool

        await redis_manager.close()

        # Should still reset the state even if pool disconnect fails
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_manager, mock_redis_client):
        """Test successful health check."""
        redis_manager.redis_client = mock_redis_client

        result = await redis_manager.health_check()

        assert result is True
        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_manager, mock_redis_client):
        """Test failed health check."""
        redis_manager.redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Ping failed")

        result = await redis_manager.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self, redis_manager):
        """Test health check when not connected."""
        result = await redis_manager.health_check()
        assert result is False

    def test_get_client_success(self, redis_manager, mock_redis_client):
        """Test successful client retrieval."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._is_connected = True

        client = redis_manager.get_client()

        assert client == mock_redis_client

    def test_get_client_not_connected(self, redis_manager):
        """Test client retrieval when not connected."""
        with pytest.raises(RuntimeError, match="Redis client not initialized or disconnected"):
            redis_manager.get_client()

    @pytest.mark.asyncio
    async def test_redis_connection_lifecycle(self, redis_manager):
        """Test complete connection lifecycle with real Redis."""
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

        # Test connection
        await redis_manager.connect()

        # Test operations
        client = redis_manager.get_client()
        await client.set("lifecycle_test", "working")
        assert await client.get("lifecycle_test") == "working"

        # Test health check
        assert await redis_manager.health_check() is True

        # Test close
        await redis_manager.close()
        assert redis_manager.redis_client is None
