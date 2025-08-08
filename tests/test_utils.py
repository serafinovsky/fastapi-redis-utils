import pytest

from fastapi_redis_utils.utils import achunked, chunked


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
