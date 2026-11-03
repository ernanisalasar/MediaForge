"""Testes de fumaça da interface (modo offscreen). Pulados se PySide6/Qt não estiver disponível."""
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from mediaforge.models.task import TaskStatus  # noqa: E402
from mediaforge.storage.history import HistoryStore  # noqa: E402
from mediaforge.storage.settings import Settings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def pump(app, cond, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def window(qapp, tmp_path, tools):
    from mediaforge.ui.main_window import MainWindow
    settings = Settings(output_dir=str(tmp_path / "saida"))
    win = MainWindow(settings, HistoryStore(tmp_path / "h.db"), tmp_path / "s.json")
    win.show()
    yield win
    win.tasks.shutdown()
    win._tmp.cleanup()


@pytest.fixture
def window_without_ffmpeg(qapp, tmp_path, monkeypatch):
    import mediaforge.ui.main_window as main_window

    tools = SimpleNamespace(ffmpeg="ffmpeg", ffprobe="ffprobe")
    encoders = {"libx264", "aac", "libvpx-vp9", "libopus", "libmp3lame", "pcm_s16le", "flac"}
    monkeypatch.setattr(main_window, "find_tools", lambda _path: tools)
    monkeypatch.setattr(main_window, "available_encoders", lambda _tools: encoders)
    win = main_window.MainWindow(
        Settings(output_dir=str(tmp_path / "saida")),
        HistoryStore(tmp_path / "history.db"),
        tmp_path / "settings.json",
    )
    win.show()
    yield win
    win.tasks.shutdown()
    win._tmp.cleanup()


def test_window_opens_with_expected_widgets(window):
    assert window.windowTitle() == "MediaForge"
    assert window.btn_settings.text() and window.btn_history.text() and window.btn_help.text()
    assert not window.btn_start.isEnabled()  # sem fonte ainda
    keys = [window.format_combo.itemData(i) for i in range(window.format_combo.count())]
    assert keys == ["mp4", "webm", "mov", "mkv"]
    window.radio_audio.setChecked(True)
    keys = [window.format_combo.itemData(i) for i in range(window.format_combo.count())]
    assert keys == ["mp3", "m4a", "wav", "flac", "opus"]


def test_local_video_convert_and_extract_audio(window, qapp, sample_video, tmp_path):
    window._set_local_files([sample_video])
    assert pump(qapp, lambda: window.info is not None)
    assert window.info.video.height == 240 and window.btn_start.isEnabled()
    # resoluções maiores ou iguais à origem ficam desabilitadas
    enabled = {window.res_combo.itemData(i): window.res_combo.model().item(i).isEnabled()
               for i in range(window.res_combo.count())}
    assert enabled["original"] and not enabled["720"] and not enabled["360"]

    window.name_edit.setText("meu_video")
    window.format_combo.setCurrentIndex(window.format_combo.findData("mkv"))
    window.btn_start.click()
    assert pump(qapp, lambda: window.tasks.tasks() and window.tasks.tasks()[-1].status.is_final)
    t = window.tasks.tasks()[-1]
    assert t.status is TaskStatus.COMPLETED, t.message
    assert (tmp_path / "saida" / "meu_video.mkv").is_file()
    assert window.btn_open.isEnabled() and window.progress.value() == 1000

    window.radio_audio.setChecked(True)
    window.format_combo.setCurrentIndex(window.format_combo.findData("mp3"))
    window.name_edit.setText("somente_audio")
    window.btn_start.click()
    assert pump(qapp, lambda: len(window.tasks.tasks()) == 2 and window.tasks.tasks()[-1].status.is_final)
    assert window.tasks.tasks()[-1].status is TaskStatus.COMPLETED
    assert (tmp_path / "saida" / "somente_audio.mp3").is_file()
    assert sample_video.exists()
    assert window.table.rowCount() == 2
    assert pump(qapp, lambda: len(window.history.list()) == 2)


def test_audio_file_disables_video_mode(window, qapp, sample_audio):
    window._set_local_files([sample_audio])
    assert pump(qapp, lambda: window.info is not None)
    assert not window.radio_video.isEnabled() and window.radio_audio.isChecked()


def test_youtube_url_uses_ytdlp_metadata_validation(window_without_ffmpeg, qapp, monkeypatch):
    from mediaforge.services.download_service import RemoteInfo

    window = window_without_ffmpeg

    class FakeService:
        def inspect_youtube(self, url):
            assert url == "https://www.youtube.com/watch?v=BaW_jenozKc"
            return RemoteInfo(
                host="www.youtube.com", filename="Vídeo de teste.mp4", content_type="video/youtube",
                size_bytes=100, is_youtube=True, duration=12, width=640, height=360,
            )

    monkeypatch.setattr(type(window), "_download_service", lambda self: FakeService())
    window.url_edit.setText("https://www.youtube.com/watch?v=BaW_jenozKc")
    window._validate_source()
    assert pump(qapp, lambda: window.remote is not None)
    assert window.remote.is_youtube and window.btn_start.isEnabled()
    assert window.info_labels["duration"].text() != "—"
    assert window.res_combo.model().item(window.res_combo.findData("720")).isEnabled() is False


def test_invalid_source_message(window, qapp):
    window.url_edit.setText("http://127.0.0.1/video.mp4")
    window._validate_source()
    assert pump(qapp, lambda: "bloqueado" in window.source_msg.text().lower())
    assert window.remote is None and not window.btn_start.isEnabled()


def test_cancel_button_cancels_running_task(window, qapp, tools, tmp_path):
    import subprocess
    big = tmp_path / "longo.mp4"
    subprocess.run([tools.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=120",
                    "-c:v", "libx264", "-preset", "ultrafast", str(big)], check=True)
    window._set_local_files([big])
    assert pump(qapp, lambda: window.info is not None)
    window.format_combo.setCurrentIndex(window.format_combo.findData("webm"))
    window.btn_start.click()
    assert pump(qapp, lambda: window.tasks.tasks() and window.tasks.tasks()[0].status is TaskStatus.RUNNING)
    assert window.btn_cancel.isEnabled()
    window.btn_cancel.click()
    assert pump(qapp, lambda: window.tasks.tasks()[0].status.is_final)
    assert window.tasks.tasks()[0].status is TaskStatus.CANCELLED
    assert big.exists()


def test_failed_followup_conversion_keeps_downloaded_original(window, qapp, tmp_path, monkeypatch):
    """O intermediário só pode ser removido depois de uma conversão concluída."""
    from mediaforge.errors import MediaServiceError
    from mediaforge.services.media_service import MediaService

    source = tmp_path / "intermediario.mp4"
    source.write_bytes(b"conteudo original")
    options = window._current_options()
    assert options is not None

    def fail_convert(self, *args, **kwargs):
        raise MediaServiceError("falha simulada")

    monkeypatch.setattr(MediaService, "convert", fail_convert)
    window._queue_convert(
        source, tmp_path / "saida", "convertido", options, delete_source_on_success=True,
    )

    assert pump(qapp, lambda: window.tasks.tasks() and window.tasks.tasks()[-1].status.is_final)
    assert window.tasks.tasks()[-1].status is TaskStatus.FAILED
    assert source.read_bytes() == b"conteudo original"


def test_remote_link_download_then_convert(window, qapp, http_server, tmp_path, monkeypatch):
    """Fluxo completo: validar link direto -> baixar -> converter (servidor local, política relaxada só no teste)."""
    from mediaforge.services.download_service import DownloadService, make_session
    from mediaforge.services.source_policy import SourcePolicy

    policy = SourcePolicy(allow_private_networks=True)
    monkeypatch.setattr(type(window), "_download_service",
                        lambda self: DownloadService(policy=policy, session=make_session(policy)))
    window.url_edit.setText(f"{http_server}/video.mp4")
    window._validate_source()
    assert pump(qapp, lambda: window.remote is not None)
    assert window.remote.filename == "video.mp4" and window.btn_start.isEnabled()
    assert window.btn_start.text() == "Baixar e converter"

    window.name_edit.setText("convertido")
    window.format_combo.setCurrentIndex(window.format_combo.findData("webm"))
    window.btn_start.click()
    assert pump(qapp, lambda: len(window.tasks.tasks()) == 2 and all(t.status.is_final for t in window.tasks.tasks()))
    kinds = [(t.kind.value, t.status) for t in window.tasks.tasks()]
    assert kinds == [("download", TaskStatus.COMPLETED), ("convert", TaskStatus.COMPLETED)], kinds
    saida = tmp_path / "saida"
    assert (saida / "convertido.webm").is_file()
    assert not (saida / "video.mp4").exists()
    # o histórico guarda só o host, nunca a URL
    hosts = {e.source_host for e in window.history.list()}
    assert "127.0.0.1" in hosts and not any("http" in e.message for e in window.history.list())


def test_remote_download_only_without_conversion(window, qapp, http_server, tmp_path, monkeypatch):
    from mediaforge.services.download_service import DownloadService, make_session
    from mediaforge.services.source_policy import SourcePolicy

    policy = SourcePolicy(allow_private_networks=True)
    monkeypatch.setattr(type(window), "_download_service",
                        lambda self: DownloadService(policy=policy, session=make_session(policy)))
    window.url_edit.setText(f"{http_server}/video.mp4")
    window._validate_source()
    assert pump(qapp, lambda: window.remote is not None)
    window.chk_convert.setChecked(False)
    assert window.btn_start.text() == "Baixar" and not window.format_combo.isEnabled()
    window.name_edit.setText("so_baixar")
    window.btn_start.click()
    assert pump(qapp, lambda: window.tasks.tasks() and window.tasks.tasks()[-1].status.is_final)
    assert len(window.tasks.tasks()) == 1
    assert (tmp_path / "saida" / "so_baixar.mp4").is_file()


def test_screenshot(window, qapp, sample_video, tmp_path):
    window._set_local_files([sample_video])
    pump(qapp, lambda: window.info is not None)
    qapp.processEvents()
    shot = tmp_path / "janela.png"
    assert window.grab().save(str(shot)) and shot.stat().st_size > 5000
    out = os.environ.get("MEDIAFORGE_SCREENSHOT")
    if out:
        window.grab().save(out)
