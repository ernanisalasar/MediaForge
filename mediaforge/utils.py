"""Funções utilitárias: formatação legível e diretórios de dados locais."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def human_size(num_bytes: int | float | None) -> str:
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def human_speed(bytes_per_second: float | None) -> str:
    if not bytes_per_second or bytes_per_second <= 0:
        return "—"
    return f"{human_size(bytes_per_second)}/s"


def app_data_dir() -> Path:
    """Pasta local de dados (histórico e configurações). Nada é enviado para fora do computador."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / "MediaForgeLocal"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_output_dir() -> Path:
    for candidate in (Path.home() / "Videos", Path.home() / "Documents", Path.home()):
        if candidate.exists():
            return candidate / "MediaForge"
    return Path.home() / "MediaForge"
