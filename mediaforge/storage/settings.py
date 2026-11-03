"""Configurações locais em JSON (sem segredos)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mediaforge.utils import default_output_dir


@dataclass
class Settings:
    output_dir: str = ""
    max_download_mb: int = 4096
    history_retention_days: int = 90
    ffmpeg_dir: str = ""
    connect_timeout: int = 10
    read_timeout: int = 30

    def __post_init__(self) -> None:
        if not self.output_dir:
            self.output_dir = str(default_output_dir())
        self.max_download_mb = min(max(int(self.max_download_mb), 1), 102400)
        self.history_retention_days = min(max(int(self.history_retention_days), 0), 3650)
        self.connect_timeout = min(max(int(self.connect_timeout), 3), 120)
        self.read_timeout = min(max(int(self.read_timeout), 5), 600)

    @property
    def max_download_bytes(self) -> int:
        return self.max_download_mb * 1024 * 1024

    @classmethod
    def load(cls, path: Path) -> "Settings":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            allowed = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**allowed)
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
