import threading
from pathlib import Path

import pytest
import requests

from mediaforge.errors import (
    DestinationExistsError, DownloadError, SizeLimitError, SourcePolicyError,
)
from mediaforge.services.download_service import (
    DownloadCancelled, DownloadService, classify_response, make_session,
)
from mediaforge.services.source_policy import SourcePolicy


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"", chunk=4):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self._chunk = chunk
        self.closed = False

    def iter_content(self, size):
        for i in range(0, len(self._body), self._chunk):
            yield self._body[i:i + self._chunk]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requested = []

    def get(self, url, **kw):
        self.requested.append(url)
        assert kw["allow_redirects"] is False and kw["stream"] is True
        return self.responses.pop(0)


def svc(public_policy, responses, **kw):
    session = FakeSession(responses)
    return DownloadService(policy=public_policy, session=session, **kw), session


def media_headers(length=None, ctype="video/mp4", **extra):
    h = {"Content-Type": ctype, **extra}
    if length is not None:
        h["Content-Length"] = str(length)
    return h


# ---------------------------------------------------------------- redirecionamentos
def test_redirect_to_private_ip_blocked(public_policy):
    s, session = svc(public_policy, [FakeResponse(302, {"Location": "http://169.254.169.254/latest/"})])
    with pytest.raises(SourcePolicyError):
        s.inspect("https://example.com/v.mp4")
    assert session.requested == ["https://example.com/v.mp4"]  # destino malicioso nunca requisitado


def test_redirect_to_loopback_hostname_blocked(public_policy):
    s, _ = svc(public_policy, [FakeResponse(301, {"Location": "http://localhost:8080/x.mp4"})])
    with pytest.raises(SourcePolicyError):
        s.inspect("https://example.com/v.mp4")


def test_direct_link_redirecting_to_youtube_is_not_a_media_file(public_policy):
    s, session = svc(public_policy, [
        FakeResponse(302, {"Location": "https://www.youtube.com/watch?v=BaW_jenozKc"}),
        FakeResponse(200, media_headers(20, ctype="text/html")),
    ])
    with pytest.raises(DownloadError, match="página web"):
        s.inspect("https://example.com/v.mp4")
    assert session.requested[-1] == "https://www.youtube.com/watch?v=BaW_jenozKc"


def test_https_to_http_downgrade_blocked(public_policy):
    s, _ = svc(public_policy, [FakeResponse(302, {"Location": "http://example.com/v.mp4"})])
    with pytest.raises(SourcePolicyError):
        s.inspect("https://example.com/v.mp4")


def test_relative_redirect_followed_and_revalidated(public_policy):
    s, session = svc(public_policy, [
        FakeResponse(302, {"Location": "/real/v.mp4"}),
        FakeResponse(200, media_headers(10)),
    ])
    info = s.inspect("https://example.com/v.mp4")
    assert session.requested[1] == "https://example.com/real/v.mp4"
    assert info.filename == "v.mp4" and info.size_bytes == 10


def test_too_many_redirects(public_policy):
    s, _ = svc(public_policy, [FakeResponse(302, {"Location": "/a"}) for _ in range(10)], max_redirects=3)
    with pytest.raises(DownloadError):
        s.inspect("https://example.com/v.mp4")


def test_redirect_without_location(public_policy):
    s, _ = svc(public_policy, [FakeResponse(302, {})])
    with pytest.raises(DownloadError):
        s.inspect("https://example.com/v.mp4")


# ---------------------------------------------------------------- classificação
@pytest.mark.parametrize("ctype,name,ok", [
    ("video/mp4", "a.mp4", True), ("audio/mpeg", "a.mp3", True), ("video/mp4; codecs=avc1", "x", True),
    ("application/octet-stream", "a.mkv", True), ("application/octet-stream", "a.exe", False),
    ("", "a.mp3", True), ("", "a", False), ("text/html; charset=utf-8", "a.mp4", False),
    ("application/json", "a.mp4", False), ("application/pdf", "a.pdf", False),
    ("application/vnd.apple.mpegurl", "stream.m3u8", False),
    ("application/dash+xml", "manifest.mpd", False),
])
def test_classify_response(ctype, name, ok):
    assert classify_response(ctype, name)[0] is ok


def test_html_page_rejected_by_inspect(public_policy):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(10, ctype="text/html"))])
    with pytest.raises(DownloadError, match="HTML"):
        s.inspect("https://example.com/pagina")


@pytest.mark.parametrize("code", [401, 403, 404, 500])
def test_http_errors(public_policy, code):
    s, _ = svc(public_policy, [FakeResponse(code)])
    with pytest.raises(DownloadError, match=str(code)):
        s.inspect("https://example.com/v.mp4")


def test_size_limit_by_content_length(public_policy):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(5000))], max_bytes=1000)
    with pytest.raises(SizeLimitError):
        s.inspect("https://example.com/v.mp4")


def test_size_limit_while_streaming_removes_temp(public_policy, tmp_path):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(), body=b"x" * 100)], max_bytes=50)
    with pytest.raises(SizeLimitError):
        s.download("https://example.com/v.mp4", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_content_disposition_filename_sanitized(public_policy):
    h = media_headers(4, **{"Content-Disposition": 'attachment; filename="../../evil.mp4"'})
    s, _ = svc(public_policy, [FakeResponse(200, h)])
    assert s.inspect("https://example.com/dl?id=1").filename == "evil.mp4"


def test_extension_added_from_content_type(public_policy):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(4, ctype="video/webm"))])
    assert s.inspect("https://example.com/download").filename.endswith(".webm")


# ---------------------------------------------------------------- download (fake)
def test_download_success_atomic_and_progress(public_policy, tmp_path):
    body = b"0123456789" * 100
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(len(body)), body=body, chunk=100)], chunk_size=100)
    events = []
    out = s.download("https://example.com/v.mp4?token=SEGREDO", tmp_path, progress_cb=events.append)
    assert out == tmp_path.resolve() / "v.mp4" and out.read_bytes() == body
    assert [p.name for p in tmp_path.iterdir()] == ["v.mp4"]  # sem .part sobrando
    assert events[-1].fraction == 1.0


def test_download_incomplete_keeps_partial_for_diagnosis(public_policy, tmp_path):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(1000), body=b"x" * 100)])
    with pytest.raises(DownloadError, match="incompleto"):
        s.download("https://example.com/v.mp4", tmp_path)
    assert any(p.name.endswith(".part") for p in tmp_path.iterdir())
    assert not (tmp_path / "v.mp4").exists()


def test_download_html_disguised_as_video_rejected(public_policy, tmp_path):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(), body=b"<!DOCTYPE html><html>x</html>")])
    with pytest.raises(DownloadError, match="HTML"):
        s.download("https://example.com/v.mp4", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_file_not_overwritten_without_confirmation(public_policy, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"original")
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(4), body=b"novo!")])
    with pytest.raises(DestinationExistsError):
        s.download("https://example.com/v.mp4", tmp_path)
    assert (tmp_path / "v.mp4").read_bytes() == b"original"


def test_overwrite_when_confirmed(public_policy, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"original")
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(5), body=b"novo!")])
    s.download("https://example.com/v.mp4", tmp_path, overwrite=True)
    assert (tmp_path / "v.mp4").read_bytes() == b"novo!"


def test_custom_filename_is_sanitized_and_gets_extension(public_policy, tmp_path):
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(4), body=b"abcd")])
    out = s.download("https://example.com/v.mp4", tmp_path, filename="../../meu:video")
    assert out.parent == tmp_path.resolve() and out.name == "meu_video.mp4"


def test_cancel_during_download_cleans_temp(public_policy, tmp_path):
    ev = threading.Event()
    ev.set()
    s, _ = svc(public_policy, [FakeResponse(200, media_headers(100), body=b"x" * 100)])
    with pytest.raises(DownloadCancelled):
        s.download("https://example.com/v.mp4", tmp_path, cancel_event=ev)
    assert list(tmp_path.iterdir()) == []


class FakeYtDlp:
    class utils:
        class DownloadError(Exception):
            pass

        class ExtractorError(Exception):
            pass


class FakeYoutubeDL:
    def __init__(self, options, info=None):
        self.options = options
        self.download_started = False
        self.info = info or {
            "id": "BaW_jenozKc", "title": "Vídeo de teste", "ext": "mp4",
            "duration": 12, "width": 640, "height": 360, "filesize_approx": 100,
        }

    def extract_info(self, url, download=False):
        assert url == "https://www.youtube.com/watch?v=BaW_jenozKc"
        if download:
            self._write_download()
        return self.info

    def process_ie_result(self, info, download=True):
        assert download is True
        self._write_download()
        return info

    def _write_download(self):
        if self.options.get("progress_hooks") is None:
            return
        self.download_started = True
        path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
        path.write_bytes(b"video")
        for hook in self.options["progress_hooks"]:
            hook({
                "status": "downloading", "downloaded_bytes": 5, "total_bytes": 5,
                "speed": 100.0, "eta": 0,
            })

    def close(self):
        pass


def fake_yt_dlp(service, info=None):
    instances = []

    def factory(options, _on_policy_error):
        ydl = FakeYoutubeDL(options, info=info)
        instances.append(ydl)
        return FakeYtDlp, ydl

    service._youtube_dl = factory
    return instances


def test_youtube_inspect_uses_mocked_metadata_and_rejects_playlists(public_policy):
    s = DownloadService(policy=public_policy)
    instances = fake_yt_dlp(s)
    info = s.inspect_youtube("https://youtu.be/BaW_jenozKc?si=tracking")
    assert info.is_youtube and info.filename == "Vídeo de teste.mp4"
    assert info.height == 360 and info.duration == 12
    assert instances[0].options["noplaylist"] is True
    assert instances[0].options["proxy"] == ""

    playlist_service = DownloadService(policy=public_policy)
    fake_yt_dlp(playlist_service, {"_type": "playlist", "entries": []})
    with pytest.raises(DownloadError, match="Playlists"):
        playlist_service.inspect_youtube("https://www.youtube.com/watch?v=BaW_jenozKc")


def test_youtube_network_uses_only_guarded_handler(public_policy):
    from yt_dlp.networking._requests import RequestsRH

    s = DownloadService(policy=public_policy)
    _, ydl = s._youtube_dl({"quiet": True}, lambda: None)
    try:
        handlers = ydl._request_director.handlers
        assert len(handlers) == 1
        handler = next(iter(handlers.values()))
        session = handler._create_instance(cookiejar=None)
        assert isinstance(handler, RequestsRH)
        assert session.trust_env is False
        assert session.max_redirects == 5
    finally:
        ydl.close()


def test_youtube_download_rejects_live_stream_before_transfer(public_policy, tmp_path):
    s = DownloadService(policy=public_policy)
    instances = fake_yt_dlp(s, {
        "id": "BaW_jenozKc", "title": "Ao vivo", "ext": "mp4", "is_live": True,
    })
    with pytest.raises(DownloadError, match="ao vivo"):
        s.download_youtube("https://youtu.be/BaW_jenozKc", tmp_path)
    assert not instances[0].download_started
    assert list(tmp_path.iterdir()) == []


def test_youtube_download_uses_temp_file_progress_and_atomic_move(public_policy, tmp_path):
    s = DownloadService(policy=public_policy)
    instances = fake_yt_dlp(s)
    progress = []
    out = s.download_youtube(
        "https://www.youtube.com/watch?v=BaW_jenozKc",
        tmp_path,
        filename="Vídeo de teste.mp4",
        progress_cb=progress.append,
    )
    assert out == tmp_path / "Vídeo de teste.mp4"
    assert out.read_bytes() == b"video"
    assert list(tmp_path.iterdir()) == [out]
    assert progress[0].fraction == 1.0 and progress[0].speed_bps == 100
    assert progress[-1].fraction == 1.0
    assert instances[0].options["noplaylist"] is True
    assert instances[0].options["format"] == "bv*+ba/b"


@pytest.mark.parametrize(
    ("audio_format", "audio_bitrate"),
    [("mp3", 192), ("m4a", 192), ("wav", None), ("flac", None), ("opus", 256)],
)
def test_youtube_audio_uses_best_audio_only_and_configures_postprocessing(
    public_policy, tmp_path, audio_format, audio_bitrate,
):
    s = DownloadService(policy=public_policy)
    instances = fake_yt_dlp(s)

    s.download_youtube(
        "https://www.youtube.com/watch?v=BaW_jenozKc",
        tmp_path,
        filename=f"audio.{audio_format}",
        audio_format=audio_format,
        audio_bitrate=audio_bitrate,
    )

    options = instances[0].options
    assert options["format"] == "bestaudio"
    assert "bv" not in options["format"]
    postprocessor = options["postprocessors"][0]
    assert postprocessor["key"] == "FFmpegExtractAudio"
    assert postprocessor["preferredcodec"] == audio_format
    if audio_format in {"wav", "flac"}:
        assert "preferredquality" not in postprocessor
    else:
        assert postprocessor["preferredquality"] == str(audio_bitrate)


def test_youtube_download_does_not_overwrite_without_confirmation(public_policy, tmp_path):
    existing = tmp_path / "Vídeo de teste.mp4"
    existing.write_bytes(b"original")
    s = DownloadService(policy=public_policy)
    fake_yt_dlp(s)
    with pytest.raises(DestinationExistsError):
        s.download_youtube(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            tmp_path,
            filename=existing.name,
        )
    assert existing.read_bytes() == b"original"


def test_youtube_download_cancelled_cleans_temporary_files(public_policy, tmp_path):
    cancel = threading.Event()
    cancel.set()
    s = DownloadService(policy=public_policy)
    fake_yt_dlp(s)
    with pytest.raises(DownloadCancelled, match="cancelado"):
        s.download_youtube(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            tmp_path,
            cancel_event=cancel,
        )
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------- servidor HTTP real (loopback)
def local_service(**kw):
    policy = SourcePolicy(allow_private_networks=True)
    return DownloadService(policy=policy, session=make_session(policy), **kw)


def test_loopback_blocked_with_real_session(http_server, tmp_path):
    policy = SourcePolicy()  # política de produção
    s = DownloadService(policy=policy, session=make_session(policy))
    with pytest.raises(SourcePolicyError):
        s.download(f"{http_server}/video.mp4", tmp_path)


def test_connection_level_check_blocks_rebinding(http_server, tmp_path, monkeypatch):
    """A validação prévia "vê" um IP público, mas a conexão real resolveria para 127.0.0.1 (DNS rebinding)."""
    import socket
    real = socket.getaddrinfo
    port = int(http_server.rsplit(":", 1)[1])

    def fake_getaddrinfo(host, p, *a, **kw):
        if host == "rebind.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return real(host, p, *a, **kw)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    policy = SourcePolicy(resolver=lambda h, p: ["93.184.216.34"])  # pré-validação passa
    s = DownloadService(policy=policy, session=make_session(policy))
    with pytest.raises(SourcePolicyError):
        s.download(f"http://rebind.example:{port}/video.mp4", tmp_path / "dl")
    assert not (tmp_path / "dl").exists() or list((tmp_path / "dl").iterdir()) == []


@pytest.mark.parametrize("target", [
    "https://169.254.169.254/latest/meta-data/",
    "http://example.com/downgrade.mp4",
])
def test_safe_session_revalidates_automatic_redirects(public_policy, target):
    class RedirectAdapter(requests.adapters.BaseAdapter):
        def send(self, request, **kwargs):
            response = requests.Response()
            response.status_code = 302
            response.headers["Location"] = target
            response.url = request.url
            response.request = request
            response._content = b""
            return response

        def close(self):
            pass

    session = make_session(public_policy)
    session.mount("https://", RedirectAdapter())
    with pytest.raises(requests.exceptions.ConnectionError, match="bloqueado"):
        session.get("https://example.com/start", timeout=1)


def test_safe_session_strips_credentials_and_proxies(public_policy, monkeypatch):
    seen = {}

    def fake_send(adapter, request, **kwargs):
        seen["headers"] = dict(request.headers)
        seen["proxies"] = kwargs["proxies"]
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response._content = b"ok"
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    session = make_session(public_policy)
    request = requests.Request(
        "GET",
        "https://example.com/video.mp4",
        headers={"Cookie": "session=secret", "Authorization": "Bearer secret", "Proxy-Authorization": "secret"},
    )
    session.send(session.prepare_request(request), allow_redirects=False)
    assert not {"Cookie", "Authorization", "Proxy-Authorization"} & seen["headers"].keys()
    assert seen["proxies"] == {} and session.trust_env is False


def test_real_download_and_redirect(http_server, tmp_path):
    out = local_service().download(f"{http_server}/redir", tmp_path)
    assert out.name == "video.mp4" and out.stat().st_size > 1000


def test_real_html_page_rejected(http_server, tmp_path):
    with pytest.raises(DownloadError):
        local_service().download(f"{http_server}/pagina.html", tmp_path)


def test_real_disguised_html_rejected(http_server, tmp_path):
    with pytest.raises(DownloadError):
        local_service().download(f"{http_server}/disfarcado.mp4", tmp_path)


def test_real_cancel_midstream(http_server, tmp_path):
    ev = threading.Event()
    seen = []

    def cb(p):
        seen.append(p)
        if not ev.is_set():
            ev.set()

    dest = tmp_path / "dl"
    with pytest.raises(DownloadCancelled):
        local_service(chunk_size=4096).download(f"{http_server}/slow.mp4", dest, cancel_event=ev, progress_cb=cb)
    assert list(dest.iterdir()) == []


def test_connection_refused_is_clear_error(tmp_path):
    with pytest.raises(DownloadError, match="conexão"):
        local_service().download("http://127.0.0.1:9/v.mp4", tmp_path)
