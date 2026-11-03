"""Ponto de entrada do MediaForge Local."""
from __future__ import annotations

import sys

from mediaforge import APP_NAME, __version__
from mediaforge.models.formats import AUDIO_FORMATS, VIDEO_FORMATS
from mediaforge.services.ffmpeg_locator import INSTALL_HELP, find_tools
from mediaforge.services.media_service import available_encoders, format_supported
from mediaforge.storage.settings import Settings
from mediaforge.utils import app_data_dir


def check_environment() -> int:
    """`python -m mediaforge --check`: verifica FFmpeg/FFprobe sem abrir a interface."""
    data_dir = app_data_dir()
    settings = Settings.load(data_dir / "settings.json")
    print(f"{APP_NAME} {__version__} | Python {sys.version.split()[0]}")
    print(f"Dados locais: {data_dir}")
    tools = find_tools(settings.ffmpeg_dir)
    if tools is None:
        print(INSTALL_HELP)
        return 1
    print(f"FFmpeg : {tools.ffmpeg}\nFFprobe: {tools.ffprobe}\n{tools.version()}")
    encoders = available_encoders(tools)
    for fmt in VIDEO_FORMATS + AUDIO_FORMATS:
        print(f"  {fmt.label:<24} {'OK' if format_supported(fmt, encoders) else 'INDISPONÍVEL (codificador ausente)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check_environment()

    from PySide6.QtWidgets import QApplication

    from mediaforge.storage.history import HistoryStore
    from mediaforge.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    data_dir = app_data_dir()
    settings_path = data_dir / "settings.json"
    settings = Settings.load(settings_path)
    history = HistoryStore(data_dir / "history.db", settings.history_retention_days)
    window = MainWindow(settings, history, settings_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
