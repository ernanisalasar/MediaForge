"""Download de links diretos de mídia autorizados.

Segurança: a URL é validada antes de cada requisição (inclusive após redirecionamentos) e o IP
é validado de novo no momento da conexão TCP, conectando-se ao IP já verificado (anti DNS rebinding).
Nenhum cookie, senha ou token é enviado ou armazenado (``trust_env=False``, sem cookie jar).
"""
from __future__ import annotations

import http.cookiejar
import math
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import unquote, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from mediaforge.errors import (
    DestinationExistsError, DownloadError, OperationCancelled, SizeLimitError, SourcePolicyError,
)
from mediaforge.models.formats import MEDIA_EXTENSIONS
from mediaforge.models.task import ProgressInfo
from mediaforge.services.fs_utils import sanitize_filename
from mediaforge.services.source_policy import (
    SourcePolicy, host_of, normalize_youtube_video_url,
)

ProgressCallback = Callable[[ProgressInfo], None]
USER_AGENT = "MediaForgeLocal/0.1 (+download direto autorizado)"

_OCTET_TYPES = {
    "application/octet-stream", "binary/octet-stream", "application/x-binary",
    "application/force-download", "application/download",
}
_MEDIA_APP_TYPES = {"application/mp4", "application/ogg", "application/x-matroska"}
_STREAM_TYPES = {
    "application/dash+xml", "application/vnd.apple.mpegurl", "application/x-mpegurl",
    "application/x-mpegurl-media",
}
_STREAM_EXTENSIONS = {".m3u8", ".mpd"}
_CTYPE_EXT = {
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov", "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi", "video/mpeg": ".mpg", "video/ogg": ".ogv", "video/3gpp": ".3gp",
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/aac": ".aac", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/flac": ".flac",
    "audio/x-flac": ".flac", "audio/ogg": ".ogg", "audio/opus": ".opus", "audio/webm": ".weba",
}


class DownloadCancelled(OperationCancelled):
    pass


class _RejectCookies(http.cookiejar.DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        _ = cookie, request
        return False

    def return_ok(self, cookie, request):
        _ = cookie, request
        return False


# ------------------------------------------------------------------ conexão segura (anti-SSRF)
def _connect_checked(conn, policy: SourcePolicy) -> socket.socket:
    host, port = conn._dns_host, conn.port
    timeout = conn.timeout if isinstance(conn.timeout, (int, float)) else None
    last_error: Optional[Exception] = None
    for family, socktype, proto, _canon, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        policy.check_resolved_ip(sockaddr[0])  # valida o IP efetivamente usado
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise last_error or OSError("Falha de conexão")


def _pool_classes(policy: SourcePolicy) -> dict:
    class _HTTPConn(HTTPConnection):
        def _new_conn(self):
            return _connect_checked(self, policy)

    class _HTTPSConn(HTTPSConnection):
        def _new_conn(self):
            return _connect_checked(self, policy)

    class _HTTPPool(HTTPConnectionPool):
        ConnectionCls = _HTTPConn

    class _HTTPSPool(HTTPSConnectionPool):
        ConnectionCls = _HTTPSConn

    return {"http": _HTTPPool, "https": _HTTPSPool}


class _SafeAdapter(HTTPAdapter):
    def __init__(self, policy: SourcePolicy, on_policy_error=None, **kwargs):
        self._policy = policy
        self._on_policy_error = on_policy_error
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = _pool_classes(self._policy)

    def send(self, request, **kwargs):
        for header in ("Cookie", "Authorization", "Proxy-Authorization"):
            request.headers.pop(header, None)
        kwargs["proxies"] = {}
        try:
            self._policy.validate_url(request.url or "")
        except SourcePolicyError as exc:
            if self._on_policy_error:
                self._on_policy_error()
            raise requests.exceptions.ConnectionError("Destino bloqueado pela política de segurança.") from exc
        return super().send(request, **kwargs)


class _SafeSession(requests.Session):
    def __init__(self, policy: SourcePolicy, on_policy_error=None):
        super().__init__()
        self._policy = policy
        self._on_policy_error = on_policy_error
        self.max_redirects = 5

    def _validate_redirect(self, previous: str, target: str) -> None:
        try:
            if urlsplit(previous).scheme.lower() == "https" and urlsplit(target).scheme.lower() != "https":
                raise SourcePolicyError("Redirecionamento de HTTPS para HTTP bloqueado.")
            self._policy.validate_url(target)
        except SourcePolicyError as exc:
            if self._on_policy_error:
                self._on_policy_error()
            raise requests.exceptions.ConnectionError(
                "Redirecionamento bloqueado pela política de segurança."
            ) from exc

    def send(self, request, **kwargs):
        try:
            self._policy.validate_url(request.url or "")
        except SourcePolicyError as exc:
            if self._on_policy_error:
                self._on_policy_error()
            raise requests.exceptions.ConnectionError(
                "Destino bloqueado pela política de segurança."
            ) from exc

        allow_redirects = kwargs.pop("allow_redirects", True)
        response = super().send(request, allow_redirects=False, **kwargs)
        if not allow_redirects:
            return response

        history = []
        current_request = request
        while response.is_redirect:
            if len(history) >= self.max_redirects:
                response.close()
                raise requests.exceptions.TooManyRedirects(
                    f"Excedidos {self.max_redirects} redirecionamentos.", response=response,
                )
            response.history = history[:]
            history.append(response)
            redirects = super().resolve_redirects(
                response,
                current_request,
                stream=kwargs.get("stream", False),
                timeout=kwargs.get("timeout"),
                verify=kwargs.get("verify", True),
                cert=kwargs.get("cert"),
                proxies={},
                yield_requests=True,
            )
            try:
                next_request = next(redirects)
            except StopIteration:
                break
            finally:
                redirects.close()
            self._validate_redirect(current_request.url or "", next_request.url or "")
            current_request = next_request
            response = super().send(current_request, allow_redirects=False, **kwargs)
        response.history = history
        return response


def make_session(policy: SourcePolicy, on_policy_error=None) -> requests.Session:
    session = _SafeSession(policy, on_policy_error=on_policy_error)
    session.trust_env = False  # ignora proxies/netrc/variáveis de ambiente
    cookies = requests.cookies.RequestsCookieJar()
    cookies.set_policy(_RejectCookies())
    session.cookies = cookies
    adapter = _SafeAdapter(policy, on_policy_error=on_policy_error, max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ------------------------------------------------------------------ classificação da resposta
def classify_response(content_type: str, filename: str) -> tuple[bool, str]:
    ctype = (content_type or "").split(";")[0].strip().lower()
    ext = Path(filename).suffix.lower()
    if ext in _STREAM_EXTENSIONS or ctype in _STREAM_TYPES:
        return False, "Playlists HLS/DASH não são suportadas; informe um arquivo de mídia direto."
    if ctype.startswith(("video/", "audio/")) or ctype in _MEDIA_APP_TYPES:
        return True, ""
    if ctype in _OCTET_TYPES or not ctype:
        if ext in MEDIA_EXTENSIONS:
            return True, ""
        return False, "Não foi possível identificar o arquivo como mídia (tipo genérico e extensão desconhecida)."
    if ctype.startswith("text/html") or ctype == "application/xhtml+xml":
        return False, "O link aponta para uma página web (HTML), não para um arquivo de mídia direto."
    return False, f"O servidor informou o tipo '{ctype}', que não é um arquivo de áudio ou vídeo."


def _filename_from_headers(headers, url: str) -> str:
    disp = headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", disp, re.I)
    if m:
        return unquote(m.group(1).strip().strip('"'))
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', disp, re.I)
    if m:
        return m.group(1).strip()
    last = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    return last or "download"


def _ensure_extension(name: str, content_type: str) -> str:
    if Path(name).suffix.lower() in MEDIA_EXTENSIONS:
        return name
    ext = _CTYPE_EXT.get((content_type or "").split(";")[0].strip().lower())
    return name + ext if ext else name


@dataclass
class RemoteInfo:
    host: str
    filename: str
    content_type: str
    size_bytes: Optional[int]
    is_youtube: bool = False
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class DownloadService:
    def __init__(
        self,
        policy: Optional[SourcePolicy] = None,
        session: Optional[requests.Session] = None,
        max_bytes: int = 4 * 1024**3,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        chunk_size: int = 256 * 1024,
        max_redirects: int = 5,
    ):
        self.policy = policy or SourcePolicy()
        self.session = session or make_session(self.policy)
        self.max_bytes = max_bytes
        self.timeout = (connect_timeout, read_timeout)
        self.chunk_size = chunk_size
        self.max_redirects = max_redirects

    # -------------------------------------------------------------- abertura com redirecionamentos
    def _open(self, url: str) -> tuple[requests.Response, str]:
        current = self.policy.validate_url(url)
        for _ in range(self.max_redirects + 1):
            try:
                resp = self.session.get(
                    current, stream=True, allow_redirects=False, timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"},
                )
            except requests.exceptions.Timeout as exc:
                raise DownloadError("Tempo esgotado ao conectar com o servidor.") from exc
            except requests.exceptions.SSLError as exc:
                raise DownloadError("Falha na verificação do certificado HTTPS do servidor.") from exc
            except requests.exceptions.ConnectionError as exc:
                if isinstance(exc.__cause__, SourcePolicyError) or "SourcePolicyError" in repr(exc):
                    raise SourcePolicyError("Destino bloqueado pela política de segurança.") from exc
                raise DownloadError("Falha de conexão com o servidor.") from exc
            except requests.exceptions.RequestException as exc:
                raise DownloadError("Erro de rede ao acessar o link.") from exc
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                resp.close()
                if not location:
                    raise DownloadError("Redirecionamento inválido (sem destino).")
                nxt = urljoin(current, location)
                if urlsplit(current).scheme == "https" and urlsplit(nxt).scheme != "https":
                    raise SourcePolicyError("Redirecionamento de HTTPS para HTTP bloqueado.")
                current = self.policy.validate_url(nxt)  # revalida cada destino
                continue
            return resp, current
        raise DownloadError("Redirecionamentos demais.")

    @staticmethod
    def _check_status(resp: requests.Response) -> None:
        code = resp.status_code
        if code in (401, 403):
            resp.close()
            raise DownloadError(
                f"O servidor negou o acesso (HTTP {code}). Esta ferramenta não aceita logins, cookies ou tokens; "
                "use apenas links diretos públicos ou autorizados."
            )
        if code != 200:
            resp.close()
            raise DownloadError(f"O servidor respondeu com HTTP {code}.")

    def _inspect_response(self, resp: requests.Response, final_url: str) -> RemoteInfo:
        ctype = resp.headers.get("Content-Type", "")
        name = _ensure_extension(
            sanitize_filename(_filename_from_headers(resp.headers, final_url), default="download"), ctype
        )
        ok, reason = classify_response(ctype, name)
        if not ok:
            resp.close()
            raise DownloadError(reason)
        try:
            size = int(resp.headers["Content-Length"]) if "Content-Length" in resp.headers else None
        except ValueError:
            size = None
        if size is not None and size > self.max_bytes:
            resp.close()
            raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
        return RemoteInfo(host=host_of(final_url), filename=name, content_type=ctype, size_bytes=size)

    def inspect(self, url: str) -> RemoteInfo:
        """Valida a fonte sem baixar o conteúdo."""
        resp, final_url = self._open(url)
        try:
            self._check_status(resp)
            return self._inspect_response(resp, final_url)
        finally:
            resp.close()

    # -------------------------------------------------------------- YouTube via yt-dlp
    def _youtube_url(self, url: str) -> str:
        normalized = normalize_youtube_video_url(url)
        self.policy.validate_url(url)
        self.policy.validate_url(normalized)
        return normalized

    def _youtube_dl(self, options: dict, on_policy_error):
        try:
            import yt_dlp
            from yt_dlp.networking._requests import RequestsRH
        except ImportError as exc:
            raise DownloadError(
                "O suporte ao YouTube não está instalado. Execute: python -m pip install -r requirements.txt"
            ) from exc

        class GuardedRequestsRH(RequestsRH):
            RH_KEY = RequestsRH.RH_KEY

            def __init__(self, policy, **kwargs):
                self._source_policy = policy
                self._on_policy_error = on_policy_error
                super().__init__(**kwargs)

            def _get_proxies(self, request):
                return {}

            def _create_instance(self, cookiejar, legacy_ssl_support=None):
                _ = cookiejar, legacy_ssl_support
                return make_session(self._source_policy, on_policy_error=self._on_policy_error)

        ydl = yt_dlp.YoutubeDL(options)
        director = getattr(ydl, "_request_director", None)
        handlers = getattr(director, "handlers", None)
        original = (
            handlers.get(RequestsRH.RH_KEY) if isinstance(handlers, dict) else None
        )
        if original is None:
            ydl.close()
            raise DownloadError("Não foi possível iniciar o cliente seguro do YouTube.")

        guarded = GuardedRequestsRH(
            self.policy,
            logger=original._logger,
            headers=original.headers,
            timeout=original.timeout,
            proxies={},
            prefer_system_certs=original.prefer_system_certs,
            verify=True,
        )
        # Nenhum handler alternativo pode ignorar as validações de redirecionamento e TCP.
        for handler in handlers.values():
            handler.close()
        handlers.clear()
        director.add_handler(guarded)
        return yt_dlp, ydl

    @staticmethod
    def _youtube_failure(exc: Exception, blocked: bool = False) -> DownloadError:
        if blocked:
            return DownloadError("Uma conexão do YouTube foi bloqueada pela política de segurança.")
        text = str(exc).lower()
        if any(term in text for term in ("private", "sign in", "login", "age", "members-only", "403",
                                         "not available in your country", "region")):
            return DownloadError(
                "O vídeo não está disponível sem autenticação (pode ser privado ou ter restrição de idade/região). "
                "O aplicativo não usa cookies, tokens ou login."
            )
        if any(term in text for term in ("timed out", "timeout", "connection", "network", "unable to download")):
            return DownloadError("Falha de conexão ao consultar ou baixar o vídeo do YouTube.")
        return DownloadError(
            "Não foi possível acessar este vídeo. Verifique se a URL é de um vídeo público e não é uma transmissão ao vivo."
        )

    @staticmethod
    def _youtube_info(info: dict, url: str) -> RemoteInfo:
        if info.get("_type") in {"playlist", "multi_video"} or info.get("entries") is not None:
            raise DownloadError("Playlists não são suportadas; informe o link de um vídeo individual.")
        if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
            raise DownloadError("Transmissões ao vivo e estreias ainda não são suportadas.")

        ext = str(info.get("ext") or "mp4").lower()
        if f".{ext}" not in MEDIA_EXTENSIONS:
            ext = "mp4"
        title = sanitize_filename(str(info.get("title") or info.get("id") or "video"), default="video")
        filename = f"{Path(title).stem or 'video'}.{ext}"
        try:
            size = int(info.get("filesize") or info.get("filesize_approx") or 0) or None
        except (TypeError, ValueError):
            size = None
        if size is not None and size <= 0:
            size = None
        try:
            duration = float(info["duration"]) if info.get("duration") is not None else None
        except (TypeError, ValueError):
            duration = None
        if duration is not None and (duration < 0 or not math.isfinite(duration)):
            duration = None
        try:
            width = int(info["width"]) if info.get("width") is not None else None
        except (TypeError, ValueError):
            width = None
        try:
            height = int(info["height"]) if info.get("height") is not None else None
        except (TypeError, ValueError):
            height = None
        width = width if width and width > 0 else None
        height = height if height and height > 0 else None
        return RemoteInfo(
            host=host_of(url),
            filename=filename,
            content_type="video/youtube",
            size_bytes=size,
            is_youtube=True,
            duration=duration,
            width=width,
            height=height,
        )

    def inspect_youtube(self, url: str) -> RemoteInfo:
        """Lê metadados de um vídeo individual sem baixar o arquivo."""
        video_url = self._youtube_url(url)
        blocked = threading.Event()
        options = {
            "format": "bv*+ba/b",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "proxy": "",
            "socket_timeout": max(self.timeout),
        }
        yt_dlp, ydl = self._youtube_dl(options, blocked.set)
        try:
            info = ydl.extract_info(video_url, download=False)
            if not isinstance(info, dict):
                raise DownloadError("O YouTube não retornou metadados válidos para este vídeo.")
            remote = self._youtube_info(info, video_url)
            if remote.size_bytes is not None and remote.size_bytes > self.max_bytes:
                raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
            return remote
        except DownloadError:
            raise
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError, OSError) as exc:
            raise self._youtube_failure(exc, blocked.is_set()) from exc
        finally:
            ydl.close()

    def download_youtube(
        self,
        url: str,
        dest_dir: Path,
        filename: Optional[str] = None,
        overwrite: bool = False,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        audio_format: Optional[str] = None,
        audio_bitrate: Optional[int] = None,
    ) -> Path:
        """Baixa um vídeo público individual do YouTube para um temporário seguro."""
        video_url = self._youtube_url(url)
        if audio_format is not None and audio_format not in {"mp3", "m4a", "wav", "flac", "opus"}:
            raise DownloadError("Formato de audio nao suportado.")
        cancel_event = cancel_event or threading.Event()
        if cancel_event.is_set():
            raise DownloadCancelled("Download cancelado.")
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(filename or "video.mp4", default="video.mp4")
        requested_path = dest_dir / safe_name
        if requested_path.exists() and not overwrite:
            raise DestinationExistsError(requested_path)

        blocked = threading.Event()
        too_large = threading.Event()
        with tempfile.TemporaryDirectory(prefix=".mediaforge-yt-", dir=dest_dir) as temp:
            temp_dir = Path(temp)

            def report(info: dict) -> None:
                if cancel_event.is_set():
                    raise DownloadCancelled("Download cancelado.")
                downloaded = info.get("downloaded_bytes") or 0
                if downloaded > self.max_bytes:
                    too_large.set()
                    raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
                if not progress_cb or info.get("status") != "downloading":
                    return
                total = info.get("total_bytes") or info.get("total_bytes_estimate")
                fraction = min(downloaded / total, 1.0) if total else None
                progress_cb(ProgressInfo(
                    fraction=fraction,
                    speed_bps=info.get("speed"),
                    eta_seconds=info.get("eta"),
                ))

            options = {
                "format": "bestaudio" if audio_format else "bv*+ba/b",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "proxy": "",
                "socket_timeout": max(self.timeout),
                "max_filesize": self.max_bytes,
                "outtmpl": str(temp_dir / "video.%(ext)s"),
                "progress_hooks": [report],
                "hls_prefer_native": True,
                "external_downloader": {},
            }
            if audio_format is not None:
                postprocessor = {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                }

                if audio_bitrate and audio_format not in {"wav", "flac"}:
                    postprocessor["preferredquality"] = str(audio_bitrate)

                options["postprocessors"] = [postprocessor]
            yt_dlp, ydl = self._youtube_dl(options, blocked.set)
            try:
                info = ydl.extract_info(video_url, download=False)
                if not isinstance(info, dict):
                    raise DownloadError("O YouTube não retornou metadados válidos para este vídeo.")
                remote = self._youtube_info(info, video_url)
                if remote.size_bytes is not None and remote.size_bytes > self.max_bytes:
                    raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
                result = ydl.process_ie_result(info, download=True)
                if cancel_event.is_set():
                    raise DownloadCancelled("Download cancelado.")
                if not isinstance(result, dict):
                    raise DownloadError("O YouTube não retornou um arquivo para download.")
            except DownloadCancelled:
                raise
            except SizeLimitError:
                raise
            except DownloadError:
                raise
            except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError, OSError) as exc:
                if cancel_event.is_set():
                    raise DownloadCancelled("Download cancelado.") from exc
                if too_large.is_set():
                    raise SizeLimitError("O arquivo excede o limite de tamanho configurado.") from exc
                if any(term in str(exc).lower() for term in ("max-filesize", "max filesize", "larger than")):
                    raise SizeLimitError("O arquivo excede o limite de tamanho configurado.") from exc
                raise self._youtube_failure(exc, blocked.is_set()) from exc
            finally:
                ydl.close()

            outputs = [p for p in temp_dir.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS]
            if len(outputs) != 1:
                raise DownloadError("O YouTube não gerou exatamente um arquivo de mídia válido.")
            downloaded_path = outputs[0]
            size = downloaded_path.stat().st_size
            if size == 0:
                raise DownloadError("O YouTube gerou um arquivo vazio.")
            if size > self.max_bytes:
                raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
            with downloaded_path.open("rb") as stream:
                self._reject_html(stream.read(512))

            final = dest_dir / f"{Path(safe_name).stem}{downloaded_path.suffix.lower()}"
            if final.exists() and (not overwrite or final != requested_path):
                raise DestinationExistsError(final)
            os.replace(downloaded_path, final)
        if progress_cb:
            progress_cb(ProgressInfo(fraction=1.0, speed_bps=None, eta_seconds=0))
        return final

    # -------------------------------------------------------------- download
    def download(
        self,
        url: str,
        dest_dir: Path,
        filename: Optional[str] = None,
        overwrite: bool = False,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Path:
        cancel_event = cancel_event or threading.Event()
        resp, final_url = self._open(url)
        tmp: Optional[Path] = None
        try:
            self._check_status(resp)
            remote = self._inspect_response(resp, final_url)
            name = sanitize_filename(filename, default=remote.filename) if filename else remote.filename
            if filename and not Path(name).suffix:
                name += Path(remote.filename).suffix
            dest_dir = Path(dest_dir).resolve()
            dest_dir.mkdir(parents=True, exist_ok=True)
            final = dest_dir / name
            if final.exists() and not overwrite:
                raise DestinationExistsError(final)
            if remote.size_bytes is not None and shutil.disk_usage(dest_dir).free < remote.size_bytes:
                raise DownloadError("Espaço em disco insuficiente na pasta de destino.")

            tmp = dest_dir / f".{final.stem}.{uuid.uuid4().hex[:8]}.part"
            total = remote.size_bytes
            done = 0
            samples: deque[tuple[float, int]] = deque(maxlen=30)
            start = last_emit = time.monotonic()
            sniff_buf = b""
            sniffed = False
            try:
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(self.chunk_size):
                        if cancel_event.is_set():
                            raise DownloadCancelled("Download cancelado.")
                        if not chunk:
                            continue
                        if not sniffed:
                            sniff_buf += chunk
                            if len(sniff_buf) >= 512:
                                sniffed = True
                                self._reject_html(sniff_buf)
                        fh.write(chunk)
                        done += len(chunk)
                        if done > self.max_bytes:
                            raise SizeLimitError("O arquivo excede o limite de tamanho configurado.")
                        now = time.monotonic()
                        samples.append((now, done))
                        if progress_cb and now - last_emit >= 0.1:
                            last_emit = now
                            progress_cb(self._progress(done, total, samples, now - start))
                if not sniffed:
                    self._reject_html(sniff_buf)
            except OperationCancelled:
                tmp.unlink(missing_ok=True)
                raise
            except (SizeLimitError, DownloadError):
                tmp.unlink(missing_ok=True)  # conteúdo rejeitado: não é útil guardar
                raise
            except requests.exceptions.Timeout as exc:
                raise DownloadError(f"Tempo esgotado durante o download. Arquivo parcial mantido em: {tmp}") from exc
            except (requests.exceptions.RequestException, OSError) as exc:
                raise DownloadError(f"Conexão interrompida durante o download. Arquivo parcial mantido em: {tmp}") from exc
            if total is not None and done < total:
                raise DownloadError(f"Download incompleto ({done} de {total} bytes). Arquivo parcial mantido em: {tmp}")
            if final.exists() and not overwrite:
                raise DestinationExistsError(final)
            os.replace(tmp, final)
            if progress_cb:
                progress_cb(ProgressInfo(fraction=1.0, speed_bps=None, eta_seconds=0))
            return final
        finally:
            resp.close()

    @staticmethod
    def _reject_html(head: bytes) -> None:
        text = head[:512].lstrip().lower()
        if text.startswith((b"<!doctype", b"<html", b"<?xml", b"<head", b"<body")) or b"<html" in text:
            raise DownloadError("O conteúdo recebido é uma página HTML, não um arquivo de mídia.")

    @staticmethod
    def _progress(done: int, total: Optional[int], samples, elapsed: float) -> ProgressInfo:
        speed = None
        if len(samples) >= 2:
            (t0, b0), (t1, b1) = samples[0], samples[-1]
            if t1 - t0 > 0.2:
                speed = (b1 - b0) / (t1 - t0)
        fraction = done / total if total else None
        eta = None
        if total and speed and speed > 0 and elapsed >= 1.5 and done >= 256 * 1024:
            eta = max(total - done, 0) / speed
        return ProgressInfo(fraction=fraction, speed_bps=speed, eta_seconds=eta)
