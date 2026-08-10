import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[None]] = set()

    def start(self, coroutine: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.exception("Background task failed", exc_info=task.exception())


task_manager = TaskManager()
