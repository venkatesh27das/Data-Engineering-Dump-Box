import asyncio
import logging
from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self, *, concurrency: int = 1) -> None:
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self._semaphore = asyncio.Semaphore(concurrency)

    def start(self, run_id: str, coroutine_factory: Callable[[], Coroutine[object, object, None]]) -> None:
        if run_id in self.tasks:
            raise ValueError(f"Run {run_id} is already queued")

        async def execute_when_available() -> None:
            async with self._semaphore:
                await coroutine_factory()

        task = asyncio.create_task(execute_when_available(), name=f"knowledge-run-{run_id}")
        self.tasks[run_id] = task
        task.add_done_callback(lambda finished: self._finished(run_id, finished))

    def cancel(self, run_id: str) -> bool:
        task = self.tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def cancel_and_wait(self, run_id: str) -> bool:
        task = self.tasks.get(run_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    def is_active(self, run_id: str) -> bool:
        task = self.tasks.get(run_id)
        return bool(task and not task.done())

    def _finished(self, run_id: str, task: asyncio.Task[None]) -> None:
        self.tasks.pop(run_id, None)
        if not task.cancelled() and task.exception():
            logger.exception("Background task failed", exc_info=task.exception())


task_manager = TaskManager()
