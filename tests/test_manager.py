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
        assert redis_manager.retry_attempts == 5
        assert redis_manager.retry_delay == 0.5
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None
        assert not redis_manager._is_connected

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

            assert redis_manager._is_connected
            assert redis_manager.redis_client == mock_redis_client
            assert redis_manager._connection_pool == mock_connection_pool
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure_then_success(self, redis_manager, mock_redis_client, mock_connection_pool):
        """Test connection with retry attempts."""
        mock_client_fail = AsyncMock(spec=redis.Redis)
        mock_client_fail.ping.side_effect = [Exception("Connection failed"), None]

        with (
            patch(
                "redis.asyncio.ConnectionPool.from_url",
                return_value=mock_connection_pool,
            ),
            patch(
                "redis.asyncio.Redis",
                side_effect=[mock_client_fail, mock_redis_client],
            ),
        ):
            await redis_manager.connect()

            assert redis_manager._is_connected
            # Check that ping was called twice
            # (first time with error, second time successfully)
            assert mock_client_fail.ping.call_count == 1
            assert mock_redis_client.ping.call_count == 1

    @pytest.mark.asyncio
    async def test_connect_all_attempts_failed(self, redis_manager):
        """Test failed connection after all attempts."""
        with patch("redis.asyncio.ConnectionPool.from_url", side_effect=Exception("Connection failed")):
            with pytest.raises(ConnectionError, match="Failed to connect to Redis after 5 attempts"):
                await redis_manager.connect()

    @pytest.mark.asyncio
    async def test_ensure_connection_when_not_connected(self, redis_manager):
        """Test ensure_connection when not connected."""
        with patch.object(redis_manager, "connect") as mock_connect:
            await redis_manager.ensure_connection()
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connection_when_already_connected(self, redis_manager):
        """Test ensure_connection when already connected."""
        redis_manager._is_connected = True
        with patch.object(redis_manager, "connect") as mock_connect:
            await redis_manager.ensure_connection()
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_close(self, redis_manager, mock_redis_client):
        """Test connection closing."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._connection_pool = MagicMock()
        redis_manager._is_connected = True

        await redis_manager.close()

        assert not redis_manager._is_connected
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_close_with_exception(self, redis_manager, mock_redis_client):
        """Test connection closing with exception."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._connection_pool = MagicMock()
        redis_manager._is_connected = True

        # Simulate exception during close
        mock_redis_client.aclose.side_effect = Exception("Close error")

        await redis_manager.close()

        # Should still reset the state even if close fails
        assert not redis_manager._is_connected
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_close_with_pool_exception(self, redis_manager, mock_redis_client):
        """Test connection closing with pool exception."""
        redis_manager.redis_client = mock_redis_client
        mock_pool = MagicMock()
        mock_pool.disconnect.side_effect = Exception("Pool disconnect error")
        redis_manager._connection_pool = mock_pool
        redis_manager._is_connected = True

        await redis_manager.close()

        # Should still reset the state even if pool disconnect fails
        assert not redis_manager._is_connected
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_manager, mock_redis_client):
        """Test successful health check."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._is_connected = True

        result = await redis_manager.health_check()

        assert result is True
        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, redis_manager, mock_redis_client):
        """Test failed health check."""
        redis_manager.redis_client = mock_redis_client
        redis_manager._is_connected = True
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
    async def test_execute_with_retry_success(self, connected_redis_manager):
        """Test successful operation execution with retry."""

        async def operation():
            return "success"

        result = await connected_redis_manager.execute_with_retry(operation)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure_then_success(self, connected_redis_manager):
        """Test operation execution with retry - failure then success."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt failed")
            return "success"

        result = await connected_redis_manager.execute_with_retry(operation)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_failed(self, connected_redis_manager):
        """Test operation execution with retry - all attempts failed."""

        async def operation():
            raise Exception("Operation failed")

        with pytest.raises(Exception, match="Operation failed"):
            await connected_redis_manager.execute_with_retry(operation)

    @pytest.mark.asyncio
    async def test_execute_with_retry_when_not_connected(self, redis_manager):
        """Test execute_with_retry when not connected - should call connect()."""

        async def operation():
            return "success"

        with patch.object(redis_manager, "connect") as mock_connect:
            result = await redis_manager.execute_with_retry(operation)

            # Verify connect was called since manager was not connected
            mock_connect.assert_called_once()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_redis_connection_lifecycle(self, redis_manager):
        """Test complete connection lifecycle with real Redis."""
        assert redis_manager._is_connected is False
        assert redis_manager.redis_client is None
        assert redis_manager._connection_pool is None

        # Test connection
        await redis_manager.connect()
        assert redis_manager._is_connected is True

        # Test operations
        client = redis_manager.get_client()
        await client.set("lifecycle_test", "working")
        assert await client.get("lifecycle_test") == "working"

        # Test health check
        assert await redis_manager.health_check() is True

        # Test close
        await redis_manager.close()
        assert redis_manager._is_connected is False
        assert redis_manager.redis_client is None
