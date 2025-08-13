from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterator, Sequence

ItemType = TypeVar("ItemType")


def chunked(items: Sequence[ItemType], chunk_size: int) -> Iterator[list[ItemType]]:
    """
    Split a sequence into consecutive chunks.

    Args:
        items: Source sequence of items
        chunk_size: Size of each chunk; must be greater than zero

    Yields:
        Lists of up to chunk_size items preserving order

    Raises:
        ValueError: If chunk_size <= 0
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    for index in range(0, len(items), chunk_size):
        yield list(items[index : index + chunk_size])


async def achunked(async_items: AsyncIterable[ItemType], chunk_size: int) -> AsyncIterator[list[ItemType]]:
    """
    Collect items from an async iterable and yield them in fixed-size chunks.

    Args:
        async_items: Async iterable producing items
        chunk_size: Size of each chunk; must be greater than zero

    Yields:
        Lists of up to chunk_size items preserving order

    Raises:
        ValueError: If chunk_size <= 0
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    batch: list[ItemType] = []
    async for item in async_items:
        batch.append(item)
        if len(batch) == chunk_size:
            yield batch
            batch = []

    if batch:
        yield batch


async def aitake(async_items: AsyncIterator[ItemType], n: int | None) -> AsyncIterator[ItemType]:
    """Take first n items from an async iterator; if n is None, yield all.

    Stops early when the iterator ends before n items.
    """
    if n is None:
        async for item in async_items:
            yield item
        return
    if n <= 0:
        return
    taken = 0
    async for item in async_items:
        yield item
        taken += 1
        if taken >= n:
            break
