"""Fila de tarefas com progresso e cancelamento. Independente da interface gráfica."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from mediaforge.errors import MediaForgeError, OperationCancelled
from mediaforge.models.task import ProgressInfo, Task, TaskStatus

Job = Callable[[Task, Callable[[ProgressInfo], None]], Optional[Path]]


class TaskManager:
    def __init__(
        self,
        on_update: Optional[Callable[[Task], None]] = None,
        on_finished: Optional[Callable[[Task], None]] = None,
        max_workers: int = 2,
    ):
        self._on_update = on_update
        self._on_finished = on_finished
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mf-task")
        self._lock = threading.RLock()
        self._tasks: dict[str, Task] = {}
        self._last_notify: dict[str, float] = {}

    # ------------------------------------------------------------------ consulta
    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def tasks(self) -> list[Task]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at)

    def active_tasks(self) -> list[Task]:
        return [t for t in self.tasks() if not t.status.is_final]

    # ------------------------------------------------------------------ operações
    def submit(self, task: Task, job: Job) -> Task:
        with self._lock:
            self._tasks[task.id] = task
        self._notify(task, force=True)
        self._executor.submit(self._run, task, job)
        return task

    def cancel(self, task_id: str) -> None:
        task = self.get(task_id)
        if task is None or task.status.is_final:
            return
        task.cancel_event.set()
        with self._lock:
            if task.status is TaskStatus.WAITING:  # ainda na fila: cancela na hora
                self._finish(task, TaskStatus.CANCELLED, "Cancelado antes de iniciar.")

    def cancel_all(self) -> None:
        for task in self.active_tasks():
            self.cancel(task.id)

    def shutdown(self) -> None:
        self.cancel_all()
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ execução
    def _run(self, task: Task, job: Job) -> None:
        with self._lock:
            if task.status is not TaskStatus.WAITING or task.cancel_event.is_set():
                return
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
        self._notify(task, force=True)
        try:
            output = job(task, lambda p: self._progress(task, p))
            if output:
                task.output_path = Path(output)
                try:
                    task.size_bytes = task.output_path.stat().st_size
                except OSError:
                    pass
            task.progress = 1.0
            self._finish(task, TaskStatus.COMPLETED, "Concluído.")
        except OperationCancelled:
            self._finish(task, TaskStatus.CANCELLED, "Operação cancelada pelo usuário.")
        except MediaForgeError as exc:
            self._finish(task, TaskStatus.FAILED, str(exc))
        except Exception as exc:  # erro inesperado: nunca derruba a fila
            self._finish(task, TaskStatus.FAILED, f"Erro inesperado ({type(exc).__name__}): {exc}")

    def _progress(self, task: Task, info: ProgressInfo) -> None:
        task.progress = info.fraction
        task.speed_bps = info.speed_bps
        task.eta_seconds = info.eta_seconds
        if info.detail:
            task.message = info.detail
        self._notify(task)

    def _finish(self, task: Task, status: TaskStatus, message: str) -> None:
        task.status = status
        task.message = message
        task.finished_at = time.time()
        task.speed_bps = task.eta_seconds = None
        self._notify(task, force=True)
        if self._on_finished:
            try:
                self._on_finished(task)
            except Exception:
                pass

    def _notify(self, task: Task, force: bool = False) -> None:
        if not self._on_update:
            return
        now = time.monotonic()
        if not force and now - self._last_notify.get(task.id, 0) < 0.1:
            return
        self._last_notify[task.id] = now
        try:
            self._on_update(task)
        except Exception:
            pass
