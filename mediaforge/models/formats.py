"""Catálogo de formatos, resoluções e qualidades de áudio suportados."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MODE_VIDEO = "video"
MODE_AUDIO = "audio"


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    extension: str
    mode: str  # "video" | "audio"
    encoders: tuple[str, ...]  # encoders FFmpeg necessários
    lossless: bool = False  # áudio sem perdas (bitrate não se aplica)
    max_bitrate: Optional[int] = None  # kbps máximos oferecidos


VIDEO_FORMATS: tuple[OutputFormat, ...] = (
    OutputFormat("mp4", "MP4 (H.264 + AAC)", ".mp4", MODE_VIDEO, ("libx264", "aac"), max_bitrate=320),
    OutputFormat("webm", "WebM (VP9 + Opus)", ".webm", MODE_VIDEO, ("libvpx-vp9", "libopus"), max_bitrate=256),
    OutputFormat("mov", "MOV (H.264 + AAC)", ".mov", MODE_VIDEO, ("libx264", "aac"), max_bitrate=320),
    OutputFormat("mkv", "MKV (H.264 + AAC)", ".mkv", MODE_VIDEO, ("libx264", "aac"), max_bitrate=320),
)

AUDIO_FORMATS: tuple[OutputFormat, ...] = (
    OutputFormat("mp3", "MP3", ".mp3", MODE_AUDIO, ("libmp3lame",), max_bitrate=320),
    OutputFormat("m4a", "M4A (AAC)", ".m4a", MODE_AUDIO, ("aac",), max_bitrate=320),
    OutputFormat("wav", "WAV (sem compressão)", ".wav", MODE_AUDIO, ("pcm_s16le",), lossless=True),
    OutputFormat("flac", "FLAC (sem perdas)", ".flac", MODE_AUDIO, ("flac",), lossless=True),
    OutputFormat("opus", "Opus", ".opus", MODE_AUDIO, ("libopus",), max_bitrate=256),
)

AUDIO_BITRATES: tuple[int, ...] = (128, 192, 256, 320)

# (chave, rótulo, altura-alvo)
RESOLUTIONS: tuple[tuple[str, str, Optional[int]], ...] = (
    ("original", "Original", None),
    ("1080", "1920 × 1080", 1080),
    ("720", "1280 × 720", 720),
    ("480", "854 × 480", 480),
    ("360", "640 × 360", 360),
)

# Codecs de áudio com perdas (para avisar que WAV/FLAC não recuperam qualidade).
LOSSY_AUDIO_CODECS = {"mp3", "aac", "opus", "vorbis", "wmav1", "wmav2", "ac3", "eac3", "amr_nb", "amr_wb"}

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp", ".ogv"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def formats_for_mode(mode: str) -> tuple[OutputFormat, ...]:
    return VIDEO_FORMATS if mode == MODE_VIDEO else AUDIO_FORMATS


def get_format(key: str, mode: str | None = None) -> OutputFormat:
    pool = VIDEO_FORMATS + AUDIO_FORMATS if mode is None else formats_for_mode(mode)
    for fmt in pool:
        if fmt.key == key:
            return fmt
    raise ValueError(f"Formato desconhecido: {key}")


def allowed_bitrates(fmt: OutputFormat) -> tuple[int, ...]:
    """Bitrates oferecidos para o formato (vazio para formatos sem perdas)."""
    if fmt.lossless or fmt.max_bitrate is None:
        return ()
    return tuple(b for b in AUDIO_BITRATES if b <= fmt.max_bitrate)
