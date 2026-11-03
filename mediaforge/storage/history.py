"""Histórico local em SQLite. Guarda apenas dados operacionais; nunca URLs completas, cookies ou tokens."""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mediaforge.models.task import Task

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    finished_at REAL NOT NULL,
    operation TEXT NOT NULL,
    file_name TEXT NOT NULL,
    output_format TEXT NOT NULL,
    status TEXT NOT NULL,
    size_bytes INTEGER,
    source_host TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT ''
)
"""


@dataclass
class HistoryEntry:
    id: int
    created_at: float
    finished_at: float
    operation: str
    file_name: str
    output_format: str
    status: str
    size_bytes: Optional[int]
    source_host: str
    message: str


class HistoryStore:
    def __init__(self, db_path: Path, retention_days: int = 90):
        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        # uma conexão por chamada: seguro para uso a partir de várias threads
        return sqlite3.connect(self.db_path, timeout=10)

    def add_task(self, task: Task) -> None:
        name = task.output_path.name if task.output_path else task.title
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO history (created_at, finished_at, operation, file_name, output_format, status,"
                " size_bytes, source_host, message) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    task.created_at, task.finished_at or time.time(), task.kind.label, name,
                    task.output_format, task.status.label, task.size_bytes, task.source_host,
                    task.message[:300],
                ),
            )

    def list(self, limit: int = 500) -> list[HistoryEntry]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, created_at, finished_at, operation, file_name, output_format, status,"
                " size_bytes, source_host, message FROM history ORDER BY finished_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [HistoryEntry(*row) for row in rows]

    def clear(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM history")

    def prune(self) -> int:
        if self.retention_days <= 0:
            return 0
        cutoff = time.time() - self.retention_days * 86400
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM history WHERE finished_at < ?", (cutoff,)).rowcount
