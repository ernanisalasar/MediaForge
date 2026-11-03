"""Localiza FFmpeg/FFprobe já instalados. Nunca baixa executáveis automaticamente."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mediaforge.errors import FFmpegMissingError
from mediaforge.services.proc import popen_kwargs

INSTALL_HELP = (
    "FFmpeg/FFprobe não foram encontrados.\n\n"
    "Instalação recomendada no Windows (PowerShell):\n"
    "    winget install Gyan.FFmpeg\n"
    "Depois feche e reabra o terminal/VS Code e confirme com:\n"
    "    ffmpeg -version\n"
    "    ffprobe -version\n\n"
    "Alternativa manual: baixe uma build oficial indicada em https://ffmpeg.org/download.html, "
    "extraia a pasta, adicione a subpasta 'bin' ao PATH ou informe essa pasta em Configurações."
)


@dataclass(frozen=True)
class FFmpegTools:
    ffmpeg: str
    ffprobe: str

    def version(self) -> str:
        try:
            out = subprocess.run(
                [self.ffmpeg, "-version"], capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace", **popen_kwargs(),
            ).stdout
            return out.splitlines()[0] if out else "versão desconhecida"
        except (OSError, subprocess.SubprocessError):
            return "versão desconhecida"


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def find_tools(extra_dir: Optional[str] = None) -> Optional[FFmpegTools]:
    """Procura, nesta ordem: pasta configurada, variável MEDIAFORGE_FFMPEG_DIR, pasta ./ffmpeg/bin, PATH."""
    candidates: list[Path] = []
    if extra_dir:
        candidates.append(Path(extra_dir))
    env_dir = os.environ.get("MEDIAFORGE_FFMPEG_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(Path.cwd() / "ffmpeg" / "bin")
    for folder in candidates:
        ffmpeg, ffprobe = folder / _exe("ffmpeg"), folder / _exe("ffprobe")
        if ffmpeg.is_file() and ffprobe.is_file():
            return FFmpegTools(str(ffmpeg.resolve()), str(ffprobe.resolve()))
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return FFmpegTools(ffmpeg, ffprobe)
    return None


def require_tools(extra_dir: Optional[str] = None) -> FFmpegTools:
    tools = find_tools(extra_dir)
    if tools is None:
        raise FFmpegMissingError(INSTALL_HELP)
    return tools
