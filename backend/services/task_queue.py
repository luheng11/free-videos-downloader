"""内存任务队列：用 asyncio 后台任务 + dict 存储状态，不引入 Redis。"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .downloader import download_video, new_task_id

logger = logging.getLogger("uvicorn.error")


class TaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    url: str
    format_id: str | None
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    filename: str | None = None
    filepath: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class TaskQueue:
    """简单的内存任务队列，支持提交下载任务与查询状态。"""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> list[Task]:
        items = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return items[:limit]

    async def submit(self, url: str, format_id: str | None = None) -> Task:
        task_id = new_task_id()
        task = Task(task_id=task_id, url=url, format_id=format_id)
        self._tasks[task_id] = task
        asyncio.create_task(self._run(task))
        return task

    async def _run(self, task: Task) -> None:
        task.status = TaskStatus.DOWNLOADING
        try:
            filepath = await asyncio.to_thread(
                download_video, task.url, task.format_id, task.task_id
            )
            task.filepath = filepath
            task.filename = os.path.basename(filepath) if filepath else None
            task.progress = 100.0
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            logger.info("任务 %s 下载完成: %s", task.task_id, task.filename)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            logger.exception("任务 %s 下载失败", task.task_id)

    def to_dict(self, task: Task) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "url": task.url,
            "status": task.status.value,
            "progress": task.progress,
            "filename": task.filename,
            "error": task.error,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        }


# 全局单例
task_queue = TaskQueue()
