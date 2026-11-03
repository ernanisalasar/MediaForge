"""Modelos de tarefa e progresso."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class TaskStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def label(self) -> str:
        return {
            TaskStatus.WAITING: "Aguardando",
            TaskStatus.RUNNING: "Em andamento",
            TaskStatus.COMPLETED: "Concluído",
            TaskStatus.CANCELLED: "Cancelado",
            TaskStatus.FAILED: "Falhou",
        }[self]

    @property
    def is_final(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)


class TaskKind(str, Enum):
    DOWNLOAD = "download"
    CONVERT = "convert"
    EXTRACT_AUDIO = "extract_audio"

    @property
    def label(self) -> str:
        return {
            TaskKind.DOWNLOAD: "Download",
            TaskKind.CONVERT: "Conversão",
            TaskKind.EXTRACT_AUDIO: "Extração de áudio",
        }[self]


@dataclass
class ProgressInfo:
    """Progresso reportado por um serviço. `fraction` é None quando não mensurável."""

    fraction: Optional[float] = None
    speed_bps: Optional[float] = None
    eta_seconds: Optional[float] = None
    detail: str = ""


@dataclass
class Task:
    kind: TaskKind
    title: str
    output_format: str = ""
    source_host: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TaskStatus = TaskStatus.WAITING
    progress: Optional[float] = 0.0
    speed_bps: Optional[float] = None
    eta_seconds: Optional[float] = None
    message: str = ""
    output_path: Optional[Path] = None
    size_bytes: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    # Chamado na thread da interface quando a tarefa conclui (ex.: encadear conversão após download).
    followup: Optional[Callable[["Task"], None]] = field(default=None, repr=False)
    followup_done: bool = field(default=False, repr=False)
