"""Inspeção de arquivos de mídia com FFprobe."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from mediaforge.errors import MediaServiceError
from mediaforge.models.formats import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from mediaforge.services.ffmpeg_locator import FFmpegTools
from mediaforge.services.proc import popen_kwargs


@dataclass
class StreamInfo:
    codec: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate: Optional[int] = None  # bits/s


@dataclass
class MediaInfo:
    path: Path
    size_bytes: int
    duration: Optional[float]
    container: str
    video: Optional[StreamInfo]
    audio: Optional[StreamInfo]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    @property
    def kind(self) -> str:
        if self.has_video:
            return "video"
        if self.has_audio:
            return "audio"
        return "unknown"


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _fps(value: Any) -> Optional[float]:
    try:
        frac = Fraction(str(value))
        return float(frac) if frac > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def parse_ffprobe(data: dict, path: Path, size_bytes: Optional[int] = None) -> MediaInfo:
    """Converte a saída JSON do FFprobe em MediaInfo (função pura, fácil de testar)."""
    video = audio = None
    for stream in data.get("streams", []):
        ctype = stream.get("codec_type")
        if ctype == "video" and video is None:
            if (stream.get("disposition") or {}).get("attached_pic"):
                continue  # capa de álbum embutida não conta como vídeo
            video = StreamInfo(
                codec=stream.get("codec_name", ""),
                width=_to_int(stream.get("width")),
                height=_to_int(stream.get("height")),
                fps=_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
                bitrate=_to_int(stream.get("bit_rate")),
            )
        elif ctype == "audio" and audio is None:
            audio = StreamInfo(
                codec=stream.get("codec_name", ""),
                sample_rate=_to_int(stream.get("sample_rate")),
                channels=_to_int(stream.get("channels")),
                bitrate=_to_int(stream.get("bit_rate")),
            )
    fmt = data.get("format", {})
    duration = _to_float(fmt.get("duration"))
    if duration is None:
        for stream in data.get("streams", []):
            duration = _to_float(stream.get("duration"))
            if duration is not None:
                break
    if size_bytes is None:
        size_bytes = _to_int(fmt.get("size")) or 0
    return MediaInfo(
        path=Path(path),
        size_bytes=size_bytes,
        duration=duration,
        container=fmt.get("format_name", ""),
        video=video,
        audio=audio,
    )


def probe(path: Path, tools: FFmpegTools, timeout: float = 60) -> MediaInfo:
    path = Path(path).resolve()
    if not path.is_file():
        raise MediaServiceError(f"Arquivo não encontrado: {path.name}")
    cmd = [
        tools.ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", "-i", str(path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, **popen_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaServiceError("O FFprobe demorou demais para ler o arquivo.") from exc
    except OSError as exc:
        raise MediaServiceError(f"Não foi possível executar o FFprobe: {exc}") from exc
    if result.returncode != 0:
        raise MediaServiceError(
            f"Não foi possível ler '{path.name}'. O arquivo pode estar corrompido ou não ser mídia válida."
        )
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaServiceError("Resposta inválida do FFprobe.") from exc
    info = parse_ffprobe(data, path, size_bytes=path.stat().st_size)
    if info.kind == "unknown":
        raise MediaServiceError(f"'{path.name}' não contém faixas de áudio ou vídeo reconhecidas.")
    return info


def is_supported_extension(path: Path) -> bool:
    return Path(path).suffix.lower() in (VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)
