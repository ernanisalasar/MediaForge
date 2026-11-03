"""Auxiliares para subprocessos: sempre listas de argumentos, nunca shell."""
from __future__ import annotations

import subprocess
import sys


def popen_kwargs() -> dict:
    """No Windows, evita abrir uma janela de console para cada processo do FFmpeg."""
    if sys.platform.startswith("win"):
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}
