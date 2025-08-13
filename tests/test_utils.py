import pytest

from fastapi_redis_utils.utils import achunked, aitake, chunked


class TestChunkUtils:
    def test_chunked_basic(self):
        items = list(range(10))
        chunks = list(chunked(items, 3))
        assert chunks == [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
            [9],
        ]

    def test_chunked_exact_division(self):
        items = [1, 2, 3, 4]
        chunks = list(chunked(items, 2))
        assert chunks == [[1, 2], [3, 4]]

    def test_chunked_single_chunk(self):
        items = [1, 2, 3]
        chunks = list(chunked(items, 10))
        assert chunks == [[1, 2, 3]]

    def test_chunked_invalid_size(self):
        with pytest.raises(ValueError):
            list(chunked([1, 2], 0))


@pytest.mark.asyncio
async def test_achunked_basic():
    async def gen():
        for i in range(7):
            yield i

    chunks = [chunk async for chunk in achunked(gen(), 3)]
    assert chunks == [[0, 1, 2], [3, 4, 5], [6]]


@pytest.mark.asyncio
async def test_achunked_exact_division():
    async def gen():
        for i in range(6):
            yield i

    chunks = [chunk async for chunk in achunked(gen(), 2)]
    assert chunks == [[0, 1], [2, 3], [4, 5]]


@pytest.mark.asyncio
async def test_achunked_invalid_size():
    async def gen():
        for i in range(3):
            yield i

    with pytest.raises(ValueError):
        _ = [chunk async for chunk in achunked(gen(), 0)]


class TestAitake:
    @pytest.mark.asyncio
    async def test_aitake_none_limit(self):
        """Test aitake with None limit (yield all items)."""

        async def gen():
            for i in range(5):
                yield i

        items = [item async for item in aitake(gen(), None)]
        assert items == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_aitake_with_limit(self):
        """Test aitake with specific limit."""

        async def gen():
            for i in range(10):
                yield i

        items = [item async for item in aitake(gen(), 3)]
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_aitake_limit_greater_than_items(self):
        """Test aitake when limit is greater than available items."""

        async def gen():
            for i in range(3):
                yield i

        items = [item async for item in aitake(gen(), 5)]
        assert items == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_aitake_zero_limit(self):
        """Test aitake with zero limit (should yield nothing)."""

        async def gen():
            for i in range(5):
                yield i

        items = [item async for item in aitake(gen(), 0)]
        assert items == []

    @pytest.mark.asyncio
    async def test_aitake_negative_limit(self):
        """Test aitake with negative limit (should yield nothing)."""

        async def gen():
            for i in range(5):
                yield i

        items = [item async for item in aitake(gen(), -1)]
        assert items == []
