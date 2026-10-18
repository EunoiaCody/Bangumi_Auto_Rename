# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 KimigaiiWuyi
# Copyright (C) 2025 EunoiaCody
"""Single-worker queue for rename tasks.

qBittorrent can fire several completion hooks at once; serialising the work
prevents two tasks from racing on the same series folder.
"""

import json
import uuid
import queue
import threading
from pathlib import Path
from typing import Any, Optional
from dataclasses import field, dataclass

from . import qbittorrent
from .logger import logger
from .utils.path import TASK_PATH


@dataclass
class QueuedTask:
    uuid: str
    path: Path
    is_anime: Optional[bool] = None
    is_movie: Optional[bool] = None
    cus_name: Optional[str] = None
    cus_season_id: Optional[int] = None
    metadata_id: Optional[int] = None
    qb_mode: bool = False
    qb_task: Any = None
    result: Any = None
    done: threading.Event = field(default_factory=threading.Event)


class TaskQueue:
    def __init__(self) -> None:
        self._queue: "queue.Queue[QueuedTask]" = queue.Queue()
        self._pending: dict[str, QueuedTask] = {}
        self._completed: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._worker = threading.Thread(
            target=self._run,
            name="rename-task-worker",
            daemon=True,
        )
        self._worker.start()

    def enqueue(self, task: QueuedTask) -> QueuedTask:
        with self._lock:
            self._pending[task.uuid] = task
        self._write_status(task, "queued")
        self._queue.put(task)
        logger.info(f"[队列] 任务 {task.uuid} 已入队: {task.path}")
        return task

    def wait(self, task_uuid: str, timeout: Optional[float] = None) -> Any:
        with self._lock:
            task = self._pending.get(task_uuid)
            if task is None:
                return self._completed.get(task_uuid)
        task.done.wait(timeout)
        return task.result

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            self._write_status(task, "running")
            try:
                from .rename.process import Rename

                task.result = Rename().process(
                    task.path,
                    task.is_anime,
                    task.is_movie,
                    task.uuid,
                    task.cus_name,
                    task.cus_season_id,
                    task.metadata_id,
                    task.qb_mode,
                )
                if task.qb_task is not None:
                    status = "success" if task.result is True else "error"
                    qbittorrent.record_index(
                        task.qb_task,
                        task_uuid=task.uuid,
                        status=status,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"[队列] 任务 {task.uuid} 异常: {exc}")
                task.result = str(exc)
                self._write_error(task, str(exc))
                if task.qb_task is not None:
                    qbittorrent.record_index(
                        task.qb_task,
                        task_uuid=task.uuid,
                        status="error",
                    )
            finally:
                task.done.set()
                with self._lock:
                    self._completed[task.uuid] = task.result
                    self._pending.pop(task.uuid, None)
                self._queue.task_done()

    @staticmethod
    def _write_status(task: QueuedTask, status: str) -> None:
        path = TASK_PATH / f"{task.uuid}.json"
        if path.exists():
            return
        payload = {
            "path": str(task.path),
            "is_anime": task.is_anime,
            "is_movie": task.is_movie,
            "name": None,
            "season_id": None,
            "uuid": task.uuid,
            "error": None,
            "status": status,
            "trigger": "qbittorrent" if task.qb_mode else "manual",
        }
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        except OSError:
            pass

    @staticmethod
    def _write_error(task: QueuedTask, error: str) -> None:
        path = TASK_PATH / f"{task.uuid}.json"
        payload = {
            "path": str(task.path),
            "is_anime": task.is_anime,
            "is_movie": task.is_movie,
            "name": None,
            "season_id": None,
            "uuid": task.uuid,
            "error": error,
            "status": "error",
            "trigger": "qbittorrent" if task.qb_mode else "manual",
        }
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        except OSError:
            pass


def new_task(**kwargs: Any) -> QueuedTask:
    return QueuedTask(uuid=str(uuid.uuid4()), **kwargs)


task_queue = TaskQueue()
