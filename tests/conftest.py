import http.server
import shutil
import socketserver
import subprocess
import threading
from pathlib import Path

import pytest

from mediaforge.services.ffmpeg_locator import find_tools
from mediaforge.services.source_policy import SourcePolicy

PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def public_policy():
    """Política com resolvedor falso: todo nome resolve para um IP público."""
    return SourcePolicy(resolver=lambda host, port: [PUBLIC_IP])


@pytest.fixture(scope="session")
def tools():
    t = find_tools()
    if t is None:
        pytest.skip("FFmpeg/FFprobe não instalados")
    return t


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory, tools):
    path = tmp_path_factory.mktemp("media") / "amostra.mp4"
    subprocess.run(
        [tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def sample_audio(tmp_path_factory, tools):
    path = tmp_path_factory.mktemp("media") / "amostra.mp3"
    subprocess.run(
        [tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "libmp3lame", "-b:a", "128k", str(path)], check=True)
    return path


@pytest.fixture
def http_server(tmp_path, sample_video):
    """Servidor HTTP local (loopback) servindo arquivos de teste. Só funciona com allow_private_networks."""
    root = tmp_path / "www"
    root.mkdir()
    shutil.copy(sample_video, root / "video.mp4")
    (root / "pagina.html").write_text("<html><body>oi</body></html>", encoding="utf-8")
    (root / "disfarcado.mp4").write_text("<!DOCTYPE html><html>falso</html>", encoding="utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/redir":
                self.send_response(302)
                self.send_header("Location", "/video.mp4")
                self.end_headers()
                return
            if self.path == "/slow.mp4":
                import time
                data = (root / "video.mp4").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(data) * 50))
                self.end_headers()
                try:
                    for _ in range(50):
                        self.wfile.write(data)
                        time.sleep(0.1)
                except OSError:
                    pass
                return
            super().do_GET()

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
