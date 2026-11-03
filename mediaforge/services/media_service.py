"""Serviço isolado que executa FFmpeg: conversão, redimensionamento e extração de áudio.

* Argumentos sempre em lista (sem shell) e caminhos sempre absolutos.
* Saída gravada em arquivo temporário ao lado do destino e só renomeada após verificação.
* O arquivo de origem nunca é alterado.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from mediaforge.errors import (
    DestinationExistsError, MediaServiceError, OperationCancelled, PathSecurityError,
)
from mediaforge.models.formats import (
    LOSSY_AUDIO_CODECS, MODE_AUDIO, MODE_VIDEO, RESOLUTIONS, OutputFormat,
    allowed_bitrates, get_format,
)
from mediaforge.models.task import ProgressInfo
from mediaforge.services.ffmpeg_locator import FFmpegTools
from mediaforge.services.fs_utils import sanitize_filename
from mediaforge.services.metadata_service import MediaInfo, probe
from mediaforge.services.proc import popen_kwargs

ProgressCallback = Callable[[ProgressInfo], None]


class ConversionCancelled(OperationCancelled):
    pass


@dataclass
class ConversionOptions:
    mode: str  # "video" | "audio"
    format_key: str
    resolution_key: str = "original"
    audio_bitrate: Optional[int] = 192  # kbps

    @property
    def fmt(self) -> OutputFormat:
        return get_format(self.format_key, self.mode)


# ---------------------------------------------------------------- opções e validação
def resolution_height(key: str) -> Optional[int]:
    for rkey, _label, height in RESOLUTIONS:
        if rkey == key:
            return height
    raise ValueError(f"Resolução desconhecida: {key}")


def available_resolutions(
    info: Optional[MediaInfo], source_height: Optional[int] = None,
) -> list[tuple[str, str, bool, str]]:
    """(chave, rótulo, habilitada, motivo). Nunca permite aumentar a resolução."""
    src_h = source_height if source_height is not None else info.video.height if info and info.video else None
    result = []
    for key, label, height in RESOLUTIONS:
        if height is None or src_h is None:
            result.append((key, label, True, ""))
        elif height < src_h:
            result.append((key, label, True, ""))
        else:
            result.append((key, label, False, f"A origem tem {src_h}p; aumentar a resolução não recupera detalhes."))
    return result


def validate_options(info: MediaInfo, opts: ConversionOptions) -> None:
    fmt = opts.fmt  # levanta ValueError para formato desconhecido
    if opts.mode == MODE_VIDEO:
        if not info.has_video:
            raise MediaServiceError("Este arquivo não tem vídeo. Escolha o modo Áudio.")
        height = resolution_height(opts.resolution_key)
        src_h = info.video.height if info.video else None
        if height is not None and src_h is not None and height >= src_h:
            raise MediaServiceError(
                f"A resolução escolhida ({height}p) não é menor que a da origem ({src_h}p). "
                "Aumentar a resolução não recupera detalhes; use 'Original'."
            )
    elif opts.mode == MODE_AUDIO:
        if not info.has_audio:
            raise MediaServiceError("Este arquivo não tem faixa de áudio para extrair.")
    else:
        raise ValueError(f"Modo desconhecido: {opts.mode}")
    if not fmt.lossless and opts.audio_bitrate is not None and opts.audio_bitrate not in allowed_bitrates(fmt):
        raise MediaServiceError(f"{opts.audio_bitrate} kbps não é suportado para {fmt.label}.")


def quality_notes(info: Optional[MediaInfo], opts: ConversionOptions) -> list[str]:
    """Avisos informativos para o usuário (não bloqueiam a operação)."""
    notes: list[str] = []
    if info is None or opts.mode != MODE_AUDIO and not info.has_audio:
        return notes
    fmt = opts.fmt
    codec = (info.audio.codec if info.audio else "").lower()
    if fmt.lossless and codec in LOSSY_AUDIO_CODECS:
        notes.append(
            f"A origem usa áudio com perdas ({codec}). Converter para {fmt.key.upper()} "
            "não recupera a qualidade que já foi perdida."
        )
    src_br = info.audio.bitrate if info.audio else None
    if not fmt.lossless and opts.audio_bitrate and src_br and codec in LOSSY_AUDIO_CODECS \
            and opts.audio_bitrate * 1000 > src_br * 1.15:
        notes.append(
            f"A origem tem cerca de {round(src_br / 1000)} kbps; escolher {opts.audio_bitrate} kbps "
            "aumenta o arquivo, mas não melhora o som."
        )
    return notes


# ---------------------------------------------------------------- construção do comando
def _can_copy_video(info: MediaInfo, opts: ConversionOptions) -> bool:
    return (
        opts.mode == MODE_VIDEO
        and opts.format_key in ("mp4", "mov", "mkv")
        and opts.resolution_key == "original"
        and info.video is not None
        and info.video.codec == "h264"
    )


def build_command(
    ffmpeg: str, src: Path, dst: Path, info: MediaInfo, opts: ConversionOptions
) -> list[str]:
    """Monta a lista de argumentos do FFmpeg. Nenhum texto do usuário é interpretado por shell."""
    fmt = opts.fmt
    cmd = [
        ffmpeg, "-hide_banner", "-nostdin", "-nostats", "-loglevel", "error",
        "-progress", "pipe:1", "-i", str(Path(src).resolve()),
    ]
    if opts.mode == MODE_VIDEO:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "0"]
        if fmt.key == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1", "-pix_fmt", "yuv420p"]
            audio_codec = "libopus"
        else:
            if _can_copy_video(info, opts):
                cmd += ["-c:v", "copy"]
            else:
                cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
            audio_codec = "aac"
        height = resolution_height(opts.resolution_key)
        if height is not None:
            cmd += ["-vf", f"scale=-2:{height}"]
        if info.has_audio:
            cmd += ["-c:a", audio_codec]
            if opts.audio_bitrate:
                cmd += ["-b:a", f"{opts.audio_bitrate}k"]
        if fmt.key == "mp4":
            cmd += ["-movflags", "+faststart"]
    else:
        cmd += ["-vn", "-map", "0:a:0", "-map_metadata", "0"]
        codec = {
            "mp3": "libmp3lame", "m4a": "aac", "wav": "pcm_s16le", "flac": "flac", "opus": "libopus",
        }[fmt.key]
        cmd += ["-c:a", codec]
        if not fmt.lossless and opts.audio_bitrate:
            cmd += ["-b:a", f"{opts.audio_bitrate}k"]
        if fmt.key == "mp3":
            cmd += ["-id3v2_version", "3"]
    cmd += ["-f", {"mkv": "matroska", "m4a": "ipod", "opus": "opus"}.get(fmt.key, fmt.key), "-y", str(Path(dst).resolve())]
    return cmd


# ---------------------------------------------------------------- encoders disponíveis
def parse_encoders(output: str) -> set[str]:
    names: set[str] = set()
    started = False
    for line in output.splitlines():
        if line.strip().startswith("---"):
            started = True
            continue
        if not started:
            continue
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6:
            names.add(parts[1])
    return names


def available_encoders(tools: FFmpegTools) -> set[str]:
    try:
        out = subprocess.run(
            [tools.ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, **popen_kwargs(),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return parse_encoders(out)


def format_supported(fmt: OutputFormat, encoders: set[str]) -> bool:
    return all(enc in encoders for enc in fmt.encoders)


# ---------------------------------------------------------------- execução
_TIME_RE = re.compile(r"^out_time_(?:us|ms)=(\d+)$")
_SPEED_RE = re.compile(r"^speed=\s*([0-9.]+)x$")


def friendly_error(stderr_lines: list[str]) -> str:
    text = "\n".join(stderr_lines)
    low = text.lower()
    if "unknown encoder" in low or "encoder not found" in low:
        return "Esta instalação do FFmpeg não inclui um codificador necessário. Instale uma build completa (ex.: winget install Gyan.FFmpeg)."
    if "invalid data found" in low or "moov atom not found" in low:
        return "O arquivo parece corrompido ou incompleto e não pôde ser processado."
    if "no such file" in low:
        return "Arquivo de origem não encontrado."
    if "permission denied" in low:
        return "Sem permissão para gravar na pasta de destino."
    if "no space left" in low:
        return "Sem espaço em disco na pasta de destino."
    tail = [ln for ln in stderr_lines if ln.strip()][-3:]
    return "O FFmpeg falhou: " + (" | ".join(tail) if tail else "erro desconhecido.")


def run_process(
    cmd: list[str],
    duration: Optional[float],
    progress_cb: Optional[ProgressCallback],
    cancel_event: Optional[threading.Event],
) -> None:
    """Executa o comando, lê o progresso (-progress pipe:1) e permite cancelamento controlado."""
    cancel_event = cancel_event or threading.Event()
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **popen_kwargs(),
        )
    except OSError as exc:
        raise MediaServiceError(f"Não foi possível iniciar o processo: {exc}") from exc

    stderr_tail: deque[str] = deque(maxlen=40)

    def drain_stderr() -> None:
        for line in proc.stderr:  # type: ignore[union-attr]
            stderr_tail.append(line.rstrip())

    cancelled = threading.Event()

    def watch_cancel() -> None:
        while proc.poll() is None:
            if cancel_event.wait(0.2):
                cancelled.set()
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return

    t_err = threading.Thread(target=drain_stderr, daemon=True)
    t_cancel = threading.Thread(target=watch_cancel, daemon=True)
    t_err.start()
    t_cancel.start()

    speed = None
    last_emit = 0.0
    for raw in proc.stdout:  # type: ignore[union-attr]
        line = raw.strip()
        m_speed = _SPEED_RE.match(line)
        if m_speed:
            speed = float(m_speed.group(1)) or None
            continue
        m_time = _TIME_RE.match(line)
        if m_time and duration and progress_cb:
            now = time.monotonic()
            if now - last_emit < 0.1:
                continue
            last_emit = now
            done = int(m_time.group(1)) / 1_000_000
            fraction = max(0.0, min(done / duration, 1.0))
            eta = (duration - done) / speed if speed and fraction > 0.02 else None
            progress_cb(ProgressInfo(fraction=fraction, eta_seconds=eta))
    returncode = proc.wait()
    t_err.join(timeout=2)
    t_cancel.join(timeout=2)
    if cancelled.is_set():
        raise ConversionCancelled("Operação cancelada.")
    if returncode != 0:
        raise MediaServiceError(friendly_error(list(stderr_tail)))


# ---------------------------------------------------------------- serviço
class MediaService:
    def __init__(self, tools: FFmpegTools):
        self.tools = tools

    @staticmethod
    def resolve_output(src: Path, dest_dir: Path, name: str, fmt: OutputFormat) -> Path:
        """Caminho final: pasta escolhida + nome sanitizado + extensão do formato.
        Nunca coincide com o arquivo de origem."""
        stem = Path(sanitize_filename(name or Path(src).stem)).stem or "arquivo"
        dest = Path(dest_dir).resolve() / f"{stem}{fmt.extension}"
        if dest == Path(src).resolve():
            dest = dest.with_name(f"{stem} (convertido){fmt.extension}")
        if dest.parent != Path(dest_dir).resolve():
            raise PathSecurityError("O caminho de destino sai da pasta escolhida.")
        return dest

    def convert(
        self,
        src: Path,
        dest_dir: Path,
        out_name: str,
        opts: ConversionOptions,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        overwrite: bool = False,
    ) -> Path:
        src = Path(src).resolve()
        info = probe(src, self.tools)
        validate_options(info, opts)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = self.resolve_output(src, dest_dir, out_name, opts.fmt)
        if dest.exists() and not overwrite:
            raise DestinationExistsError(dest)
        tmp = dest.with_name(f".{dest.stem}.{uuid.uuid4().hex[:8]}.part{dest.suffix}")
        cmd = build_command(self.tools.ffmpeg, src, tmp, info, opts)
        try:
            run_process(cmd, info.duration, progress_cb, cancel_event)
            self._verify_output(tmp, opts)
        except OperationCancelled:
            tmp.unlink(missing_ok=True)  # arquivo próprio e incompleto: seguro remover
            raise
        except MediaServiceError as exc:
            if tmp.exists():  # mantido para diagnóstico
                raise MediaServiceError(f"{exc}\n(Saída parcial mantida para diagnóstico: {tmp})") from exc
            raise
        if dest.exists() and not overwrite:
            raise DestinationExistsError(dest)
        os.replace(tmp, dest)
        if progress_cb:
            progress_cb(ProgressInfo(fraction=1.0))
        return dest

    def _verify_output(self, path: Path, opts: ConversionOptions) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise MediaServiceError("O FFmpeg terminou, mas nenhum arquivo foi gerado.")
        try:
            out = probe(path, self.tools)
        except MediaServiceError as exc:
            raise MediaServiceError("O arquivo gerado não pôde ser lido na verificação final.") from exc
        if opts.mode == MODE_VIDEO and not out.has_video:
            raise MediaServiceError("O arquivo gerado não contém vídeo.")
        if opts.mode == MODE_AUDIO and not out.has_audio:
            raise MediaServiceError("O arquivo gerado não contém áudio.")

    def make_thumbnail(self, src: Path, out_png: Path, at_seconds: float = 1.0) -> bool:
        """Extrai um quadro para a pré-visualização. Devolve False se não for possível."""
        cmd = [
            self.tools.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-ss", f"{max(at_seconds, 0):.2f}", "-i", str(Path(src).resolve()),
            "-frames:v", "1", "-vf", "scale=480:-2", "-y", str(Path(out_png).resolve()),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, stdin=subprocess.DEVNULL, **popen_kwargs())
        except (OSError, subprocess.SubprocessError):
            return False
        return Path(out_png).is_file() and Path(out_png).stat().st_size > 0
