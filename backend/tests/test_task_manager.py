import asyncio

import pytest

from app.services.task_manager import TaskManager


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_task_manager_queues_work_at_configured_concurrency() -> None:
    manager = TaskManager(concurrency=1)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def first() -> None:
        first_started.set()
        await release_first.wait()

    async def second() -> None:
        second_started.set()

    manager.start("first", first)
    manager.start("second", second)
    await first_started.wait()
    await asyncio.sleep(0)
    assert not second_started.is_set()

    release_first.set()
    await second_started.wait()
    await asyncio.gather(*manager.tasks.values())
    assert not manager.is_active("first")
    assert not manager.is_active("second")


@pytest.mark.anyio
async def test_task_manager_can_cancel_queued_work_without_creating_coroutine() -> None:
    manager = TaskManager(concurrency=1)
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def first() -> None:
        await release_first.wait()

    async def second() -> None:
        second_started.set()

    manager.start("first", first)
    manager.start("second", second)
    await asyncio.sleep(0)
    assert await manager.cancel_and_wait("second")
    assert not second_started.is_set()

    release_first.set()
    await manager.tasks["first"]
