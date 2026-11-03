"""Janela principal do MediaForge Local."""
from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from mediaforge import APP_NAME
from mediaforge.errors import DestinationExistsError, FFmpegMissingError, MediaForgeError
from mediaforge.models.formats import (
    MODE_AUDIO, MODE_VIDEO, VIDEO_EXTENSIONS, allowed_bitrates, formats_for_mode,
)
from mediaforge.models.task import Task, TaskKind, TaskStatus
from mediaforge.services.download_service import DownloadService, RemoteInfo
from mediaforge.services.ffmpeg_locator import INSTALL_HELP, FFmpegTools, find_tools
from mediaforge.services.fs_utils import sanitize_filename, unique_path
from mediaforge.services.media_service import (
    ConversionOptions, MediaService, available_encoders, available_resolutions, format_supported,
    quality_notes,
)
from mediaforge.services.metadata_service import MediaInfo, is_supported_extension, probe
from mediaforge.services.source_policy import STUDIO_URL, TAKEOUT_URL, is_youtube_url
from mediaforge.services.task_manager import TaskManager
from mediaforge.storage.history import HistoryStore
from mediaforge.storage.settings import Settings
from mediaforge.ui.dialogs import HelpDialog, HistoryDialog, SettingsDialog
from mediaforge.ui.styles import DANGER, MUTED, OK, STYLESHEET
from mediaforge.utils import human_duration, human_size, human_speed

SUPPORTED_FILTER = (
    "Mídia (*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.wmv *.flv *.mpg *.mpeg *.ts *.m2ts *.3gp *.ogv "
    "*.mp3 *.m4a *.aac *.wav *.flac *.ogg *.oga *.opus *.wma *.aiff *.aif);;Todos os arquivos (*)"
)


class _WorkerSignals(QObject):
    finished = Signal(object, object, object)  # worker, resultado, erro


class _Worker(QRunnable):
    """Executa uma função bloqueante fora da thread da interface."""

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self.fn = fn
        self.signals = _WorkerSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result, error = self.fn(), None
        except MediaForgeError as exc:
            result, error = None, str(exc)
        except Exception as exc:  # noqa: BLE001
            result, error = None, f"Erro inesperado ({type(exc).__name__}): {exc}"
        self.signals.finished.emit(self, result, error)


def _set_item_enabled(combo: QComboBox, index: int, enabled: bool, tooltip: str = "") -> None:
    item = combo.model().item(index)
    if item is not None:
        item.setEnabled(enabled)
        item.setToolTip(tooltip)


def _first_enabled(combo: QComboBox) -> int:
    for i in range(combo.count()):
        if combo.model().item(i).isEnabled():
            return i
    return -1


class MainWindow(QMainWindow):
    task_changed = Signal(object)

    def __init__(self, settings: Settings, history: HistoryStore, settings_path: Path):
        super().__init__()
        self.settings = settings
        self.history = history
        self.settings_path = settings_path
        self.setWindowTitle("MediaForge")
        icon_path = Path(__file__).resolve().parent / "assets" / "square-letter-m.svg"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1180, 900)
        self.setMinimumSize(760, 520)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLESHEET)

        self.tools: Optional[FFmpegTools] = None
        self.encoders: set[str] = set()
        self.local_files: list[Path] = []
        self.info: Optional[MediaInfo] = None
        self.remote: Optional[RemoteInfo] = None
        self.remote_url: Optional[str] = None
        self.current_task_id: Optional[str] = None
        self.last_output: Optional[Path] = None
        self._rows: dict[str, int] = {}
        self._workers: set[_Worker] = set()
        self._pool = QThreadPool.globalInstance()
        self._tmp = tempfile.TemporaryDirectory(prefix="mediaforge_")  # somente miniaturas próprias

        self.tasks = TaskManager(
            on_update=lambda t: self.task_changed.emit(t), on_finished=self._record_history,
        )
        self.task_changed.connect(self._on_task_changed)
        self._build_ui()
        self._refresh_tools()
        self._on_mode_changed()

    # ================================================================== construção da interface
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        # Em telas pequenas o conteúdo rola em vez de ter widgets sobrepostos.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        # ---- cabeçalho
        header = QFrame()
        header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 10, 16, 10)
        title = QLabel("MediaForge")
        title.setObjectName("title")
        h.addWidget(title)
        h.addStretch(1)
        self.btn_settings = QPushButton("Configurações")
        self.btn_history = QPushButton("Histórico")
        self.btn_help = QPushButton("Ajuda")
        for b in (self.btn_settings, self.btn_history, self.btn_help):
            h.addWidget(b)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_history.clicked.connect(self._open_history)
        self.btn_help.clicked.connect(lambda: HelpDialog(self).exec())
        outer.addWidget(header)

        # ---- aviso de FFmpeg ausente
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        self.banner_label = QLabel(INSTALL_HELP)
        self.banner_label.setWordWrap(True)
        self.banner_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        recheck = QPushButton("Verificar novamente")
        recheck.clicked.connect(self._refresh_tools)
        bl.addWidget(self.banner_label, 1)
        bl.addWidget(recheck, 0, Qt.AlignTop)
        outer.addWidget(self.banner)

        # ---- duas colunas
        cols = QHBoxLayout()
        cols.setSpacing(12)
        cols.addWidget(self._build_left(), 5)
        cols.addWidget(self._build_right(), 4)
        outer.addLayout(cols, 1)

        outer.addWidget(self._build_queue())
        outer.addWidget(self._build_footer())

    def _panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("h2")
        lay.addWidget(label)
        return frame, lay

    def _build_left(self) -> QFrame:
        frame, lay = self._panel("Fonte e informações")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Cole um link direto de mídia ou um vídeo individual do YouTube")
        self.url_edit.returnPressed.connect(self._validate_source)
        lay.addWidget(self.url_edit)
        row = QHBoxLayout()
        self.btn_validate = QPushButton("Validar fonte")
        self.btn_files = QPushButton("Selecionar arquivos…")
        self.btn_validate.clicked.connect(self._validate_source)
        self.btn_files.clicked.connect(self._pick_files)
        row.addWidget(self.btn_validate)
        row.addWidget(self.btn_files)
        row.addStretch(1)
        lay.addLayout(row)

        self.preview = QLabel("Arraste arquivos de vídeo ou áudio para cá\nou use “Selecionar arquivos…”")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(170)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # a imagem nunca redimensiona o layout
        lay.addWidget(self.preview, 1)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.info_labels: dict[str, QLabel] = {}
        for key, text in (
            ("name", "Nome"), ("ext", "Extensão / tamanho"), ("duration", "Duração"),
            ("video", "Vídeo"), ("audio", "Áudio"),
        ):
            key_label = QLabel(text)
            key_label.setObjectName("infoKey")
            value = QLabel("—")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.info_labels[key] = value
            form.addRow(key_label, value)
        lay.addLayout(form)

        self.source_msg = QLabel("")
        self.source_msg.setWordWrap(True)
        self.source_msg.setObjectName("muted")
        lay.addWidget(self.source_msg)

        short = QHBoxLayout()
        hint = QLabel("Seus próprios conteúdos:")
        hint.setObjectName("muted")
        b1, b2 = QPushButton("YouTube Studio"), QPushButton("Google Takeout")
        for b, url in ((b1, STUDIO_URL), (b2, TAKEOUT_URL)):
            b.setObjectName("link")
            b.setToolTip(url)
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        short.addWidget(hint)
        short.addWidget(b1)
        short.addWidget(b2)
        short.addStretch(1)
        lay.addLayout(short)
        return frame

    def _build_right(self) -> QFrame:
        frame, lay = self._panel("Formato e processamento")
        mode_row = QHBoxLayout()
        self.radio_video, self.radio_audio = QRadioButton("Vídeo"), QRadioButton("Áudio")
        self.radio_video.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_video)
        self.mode_group.addButton(self.radio_audio)
        self.radio_video.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.radio_video)
        mode_row.addWidget(self.radio_audio)
        mode_row.addStretch(1)
        lay.addLayout(mode_row)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.format_combo, self.res_combo, self.quality_combo = QComboBox(), QComboBox(), QComboBox()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.res_combo.currentIndexChanged.connect(self._update_notes)
        self.quality_combo.currentIndexChanged.connect(self._update_notes)
        form.addRow("Formato de saída", self.format_combo)
        form.addRow("Resolução", self.res_combo)
        form.addRow("Qualidade do áudio", self.quality_combo)
        lay.addLayout(form)

        self.notes = QLabel("")
        self.notes.setObjectName("note")
        self.notes.setWordWrap(True)
        lay.addWidget(self.notes)

        self.chk_convert = QCheckBox("Converter para o formato escolhido após baixar")
        self.chk_convert.setChecked(True)
        self.chk_convert.toggled.connect(self._on_convert_toggled)
        lay.addWidget(self.chk_convert)

        form2 = QFormLayout()
        form2.setHorizontalSpacing(14)
        form2.setVerticalSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nome do arquivo final (sem extensão)")
        form2.addRow("Nome do arquivo", self.name_edit)
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(self.settings.output_dir)
        btn_dir = QPushButton("Procurar…")
        btn_dir.clicked.connect(self._pick_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_dir)
        form2.addRow("Pasta de destino", dir_row)
        lay.addLayout(form2)
        lay.addStretch(1)

        self.btn_start = QPushButton("Iniciar")
        self.btn_start.setObjectName("primary")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        lay.addWidget(self.btn_start)
        return frame

    def _build_queue(self) -> QFrame:
        frame, lay = self._panel("Fila de tarefas")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tarefa", "Tipo", "Estado", "Progresso", "Detalhes"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setFixedHeight(100)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        lay.addWidget(self.table)
        return frame

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        lay.addWidget(self.progress)
        row = QHBoxLayout()
        self.state_label = QLabel("Pronto.")
        self.state_label.setWordWrap(True)
        self.speed_label = QLabel("")
        self.speed_label.setObjectName("muted")
        self.eta_label = QLabel("")
        self.eta_label.setObjectName("muted")
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_open = QPushButton("Abrir pasta")
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_show = QPushButton("Mostrar arquivo")
        self.btn_show.clicked.connect(self._show_file)
        self.btn_open.setEnabled(False)
        self.btn_show.setEnabled(False)
        row.addWidget(self.state_label, 1)
        row.addWidget(self.speed_label)
        row.addWidget(self.eta_label)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_show)
        row.addWidget(self.btn_open)
        lay.addLayout(row)
        return frame

    # ================================================================== ferramentas
    def _refresh_tools(self) -> None:
        self.tools = find_tools(self.settings.ffmpeg_dir)
        self.encoders = available_encoders(self.tools) if self.tools else set()
        self.banner.setVisible(self.tools is None)
        self._populate_formats()
        self._update_start_enabled()

    # ================================================================== trabalhadores em segundo plano
    def _run_async(self, fn, on_done, on_fail=None) -> None:
        worker = _Worker(fn)
        worker.on_done, worker.on_fail = on_done, on_fail  # type: ignore[attr-defined]
        worker.signals.finished.connect(self._on_worker_finished)
        self._workers.add(worker)
        self._pool.start(worker)

    @Slot(object, object, object)
    def _on_worker_finished(self, worker: _Worker, result, error) -> None:
        self._workers.discard(worker)
        if error is None:
            worker.on_done(result)  # type: ignore[attr-defined]
        elif getattr(worker, "on_fail", None):
            worker.on_fail(error)  # type: ignore[attr-defined]
        else:
            self.source_msg.setText(f"<span style='color:{DANGER}'>{error}</span>")

    # ================================================================== fonte: link direto
    def _validate_source(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self._set_msg("Cole um link direto ou de um vídeo do YouTube para validar.", error=True)
            return
        self.btn_validate.setEnabled(False)
        self._set_msg("Validando a fonte…")
        service = self._download_service()

        def work():
            if is_youtube_url(url):
                return service.inspect_youtube(url)
            return service.inspect(url)

        def done(remote: RemoteInfo):
            self.btn_validate.setEnabled(True)
            self._apply_remote(url, remote)

        def fail(msg: str):
            self.btn_validate.setEnabled(True)
            self.remote = self.remote_url = None
            self._set_msg(msg, error=True)
            self._update_start_enabled()

        self._run_async(work, done, fail)

    def _apply_remote(self, url: str, remote: RemoteInfo) -> None:
        self.remote, self.remote_url = remote, url
        self.local_files, self.info = [], None
        stem, ext = Path(remote.filename).stem, Path(remote.filename).suffix
        self._clear_info()
        self.info_labels["name"].setText(remote.filename)
        self.info_labels["ext"].setText(f"{ext or '—'} / {human_size(remote.size_bytes)}")
        if remote.is_youtube:
            self.info_labels["duration"].setText(human_duration(remote.duration))
            self.info_labels["video"].setText(
                f"{remote.width}×{remote.height}" if remote.width and remote.height
                else "Vídeo; resolução detalhada após o download"
            )
            self.info_labels["audio"].setText("Faixa de áudio disponível")
            self.preview.setPixmap(QPixmap())
            self.preview.setText("A miniatura será gerada localmente após o download.")
            self.name_edit.setEnabled(True)
            self.name_edit.setText(stem)
            self._set_modes_available(video=True, audio=True)
            self.radio_video.setChecked(True)
            self._set_msg(
                "Metadados públicos do YouTube carregados. Baixe apenas conteúdo próprio ou autorizado.",
                ok=True,
            )
            self._on_mode_changed()
            self._on_convert_toggled()
            return
        self.info_labels["duration"].setText("disponível após o download")
        self.info_labels["video"].setText(f"Tipo informado: {remote.content_type or 'não informado'}")
        self.info_labels["audio"].setText(f"Servidor: {remote.host}")
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Fonte validada.\nA pré-visualização aparece depois do download.")
        self.name_edit.setEnabled(True)
        self.name_edit.setText(stem)
        is_audio = (remote.content_type or "").lower().startswith("audio/") or ext.lower() in {
            ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif"}
        self._set_modes_available(video=not is_audio, audio=True)
        (self.radio_audio if is_audio else self.radio_video).setChecked(True)
        self._set_msg("Fonte validada: o servidor entrega um arquivo de mídia. Use apenas conteúdo que você tem direito de baixar.", ok=True)
        self._on_mode_changed()
        self._on_convert_toggled()

    # ================================================================== fonte: arquivos locais
    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar mídia", "", SUPPORTED_FILTER)
        if files:
            self._set_local_files([Path(f) for f in files])

    def _set_local_files(self, paths: list[Path]) -> None:
        valid = [p for p in paths if p.is_file() and is_supported_extension(p)]
        if not valid:
            self._set_msg("Nenhum arquivo de vídeo/áudio compatível foi selecionado.", error=True)
            return
        if len(valid) < len(paths):
            self._set_msg(f"{len(paths) - len(valid)} arquivo(s) ignorado(s) por não serem mídia compatível.", error=True)
        self.local_files = valid
        self.remote = self.remote_url = None
        self.url_edit.clear()
        self.chk_convert.setVisible(False)
        self._clear_info()
        first = valid[0]
        self.info_labels["name"].setText(first.name + (f"  (+{len(valid) - 1} arquivos)" if len(valid) > 1 else ""))
        self._set_msg("Lendo metadados…")
        if len(valid) == 1:
            self.name_edit.setEnabled(True)
            self.name_edit.setText(first.stem)
        else:
            self.name_edit.setEnabled(False)
            self.name_edit.setText("")
            self.name_edit.setPlaceholderText("(cada arquivo mantém o nome original)")
        if self.tools is None:
            self._set_msg("Instale o FFmpeg/FFprobe para ler e converter arquivos.", error=True)
            self._update_start_enabled()
            return
        tools, tmp = self.tools, Path(self._tmp.name)

        def work():
            info = probe(first, tools)
            thumb = None
            if info.has_video:
                out = tmp / f"thumb_{int(time.time() * 1000)}.png"
                at = min(1.0, (info.duration or 0) / 2)
                if MediaService(tools).make_thumbnail(first, out, at):
                    thumb = out
            return info, thumb

        def done(res):
            info, thumb = res
            if self.local_files and self.local_files[0] == first:
                self._apply_local_info(info, thumb)

        def fail(msg: str):
            self.info = None
            self._set_msg(msg, error=True)
            self._update_start_enabled()

        self._run_async(work, done, fail)

    def _apply_local_info(self, info: MediaInfo, thumb: Optional[Path]) -> None:
        self.info = info
        v, a = info.video, info.audio
        self.info_labels["ext"].setText(f"{info.extension or '—'} / {human_size(info.size_bytes)}")
        self.info_labels["duration"].setText(human_duration(info.duration))
        if v:
            fps = f", {v.fps:.0f} fps" if v.fps else ""
            self.info_labels["video"].setText(f"{v.width}×{v.height}, codec {v.codec}{fps}")
        else:
            self.info_labels["video"].setText("— (somente áudio)")
        if a:
            ch = {1: "mono", 2: "estéreo"}.get(a.channels or 0, f"{a.channels} canais" if a.channels else "")
            sr = f"{a.sample_rate / 1000:g} kHz" if a.sample_rate else ""
            br = f"{round(a.bitrate / 1000)} kbps" if a.bitrate else ""
            self.info_labels["audio"].setText(", ".join(x for x in (f"codec {a.codec}", sr, ch, br) if x))
        else:
            self.info_labels["audio"].setText("— (sem faixa de áudio)")
        if thumb and thumb.exists():
            pm = QPixmap(str(thumb))
            w, h = max(self.preview.width(), 320) - 12, max(self.preview.height(), 200) - 12
            self.preview.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("♪  Arquivo de áudio" if not info.has_video else "Sem pré-visualização")
        multi = len(self.local_files) > 1
        self._set_modes_available(video=info.has_video or multi, audio=info.has_audio or multi)
        if not info.has_video:
            self.radio_audio.setChecked(True)
        self._set_msg(self._compat_message(info), ok=True)
        self._on_mode_changed()

    @staticmethod
    def _compat_message(info: MediaInfo) -> str:
        if info.has_video and info.has_audio:
            return (f"Vídeo ({info.video.codec}) com áudio ({info.audio.codec}). Compatível: converter para "
                    "MP4/WebM/MOV/MKV ou extrair o áudio.")
        if info.has_video:
            return "Este vídeo não tem faixa de áudio: a extração de áudio não está disponível."
        return "Arquivo somente de áudio: formatos de vídeo indisponíveis; converta para outro formato de áudio."

    def _clear_info(self) -> None:
        for label in self.info_labels.values():
            label.setText("—")

    # ================================================================== arrastar e soltar
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls and all(u.isLocalFile() for u in urls):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._set_local_files(paths)

    # ================================================================== formato / opções
    def _mode(self) -> str:
        return MODE_VIDEO if self.radio_video.isChecked() else MODE_AUDIO

    def _on_mode_changed(self) -> None:
        self._populate_formats()
        self._sync_controls()
        self._update_notes()
        self._update_start_enabled()

    def _set_modes_available(self, video: bool, audio: bool) -> None:
        self._modes_ok = {MODE_VIDEO: video, MODE_AUDIO: audio}
        self._sync_controls()

    def _sync_controls(self) -> None:
        """Habilita os modos e as opcoes conforme a fonte."""
        active = self._convert_active()
        remote_youtube = self.remote is not None and self.remote.is_youtube
        ok = getattr(self, "_modes_ok", {MODE_VIDEO: True, MODE_AUDIO: True})

        self.radio_video.setEnabled((active or remote_youtube) and ok[MODE_VIDEO])
        self.radio_audio.setEnabled((active or remote_youtube) and ok[MODE_AUDIO])
        self.format_combo.setEnabled(active)
        self.res_combo.setEnabled(active and self._mode() == MODE_VIDEO)
        has_rates = self.quality_combo.currentData() is not None
        self.quality_combo.setEnabled(active and has_rates)

    def _convert_active(self) -> bool:
        # No YouTube, o modo Audio sempre precisa das opcoes de formato.
        if (
            self.remote is not None
            and self.remote.is_youtube
            and self._mode() == MODE_AUDIO
        ):
            return True
        return not (
            self.remote is not None
            and not self.chk_convert.isChecked()
        )

    def _on_convert_toggled(self, *_args) -> None:
        is_remote = self.remote is not None
        self.chk_convert.setVisible(is_remote)
        self._populate_formats()
        self._sync_controls()
        self._update_start_enabled()

    def _populate_formats(self) -> None:
        mode = self._mode()
        previous = self.format_combo.currentData()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for fmt in formats_for_mode(mode):
            self.format_combo.addItem(fmt.label, fmt.key)
            ok = format_supported(fmt, self.encoders) if self.tools else False
            _set_item_enabled(self.format_combo, self.format_combo.count() - 1, ok,
                              "" if ok else "Sem suporte nesta instalação do FFmpeg (codificador ausente).")
        idx = max(self.format_combo.findData(previous), 0)
        if not self.format_combo.model().item(idx).isEnabled():
            idx = max(_first_enabled(self.format_combo), 0)
        self.format_combo.setCurrentIndex(idx)
        self.format_combo.blockSignals(False)
        self._populate_resolutions()
        self._populate_quality()

    def _populate_resolutions(self) -> None:
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        source_height = None
        if self.remote and self.remote.is_youtube:
            source_height = self.info.video.height if self.info and self.info.video else self.remote.height
        for key, label, enabled, reason in available_resolutions(self.info, source_height=source_height):
            self.res_combo.addItem(label, key)
            _set_item_enabled(self.res_combo, self.res_combo.count() - 1, enabled, reason)
        self.res_combo.setCurrentIndex(0)
        self.res_combo.blockSignals(False)

    def _populate_quality(self) -> None:
        fmt_key = self.format_combo.currentData()
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        if fmt_key:
            fmt = next(f for f in formats_for_mode(self._mode()) if f.key == fmt_key)
            rates = allowed_bitrates(fmt)
            if rates:
                for r in rates:
                    self.quality_combo.addItem(f"{r} kbps", r)
                self.quality_combo.setCurrentIndex(min(1, len(rates) - 1))
            else:
                self.quality_combo.addItem("Sem perdas (não se aplica)", None)
        self.quality_combo.blockSignals(False)
        self._sync_controls()

    def _on_format_changed(self) -> None:
        self._populate_quality()
        self._update_notes()
        self._update_start_enabled()

    def _current_options(self) -> Optional[ConversionOptions]:
        key = self.format_combo.currentData()
        if not key:
            return None
        return ConversionOptions(
            mode=self._mode(), format_key=key, resolution_key=self.res_combo.currentData() or "original",
            audio_bitrate=self.quality_combo.currentData(),
        )

    def _update_notes(self) -> None:
        opts = self._current_options()
        notes = quality_notes(self.info, opts) if (opts and self.info) else []
        if opts and self._mode() == MODE_AUDIO and opts.fmt.lossless and not self.info:
            notes.append("Converter áudio com perdas (MP3, AAC, Opus) para WAV/FLAC não recupera a qualidade original.")
        self.notes.setText("\n".join(notes))

    def _update_start_enabled(self) -> None:
        has_source = bool(self.local_files) or self.remote is not None
        ready = self.tools is not None and has_source and bool(self.dir_edit.text().strip())

        if self.local_files and self.info is None:
            ready = False

        if self._convert_active() and self.format_combo.currentData() is None:
            ready = False

        self.btn_start.setEnabled(ready)

        if self.remote is not None:
            if self.remote.is_youtube and self._mode() == MODE_AUDIO:
                self.btn_start.setText("Baixar áudio")
            else:
                self.btn_start.setText(
                    "Baixar e converter" if self.chk_convert.isChecked() else "Baixar"
                )
        else:
            self.btn_start.setText(
                "Extrair áudio" if self._mode() == MODE_AUDIO else "Converter"
            )

    def _pick_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pasta de destino", self.dir_edit.text())
        if folder:
            self.dir_edit.setText(folder)
            self._update_start_enabled()

    # ================================================================== iniciar tarefas
    def _download_service(self) -> DownloadService:
        from mediaforge.services.download_service import make_session
        from mediaforge.services.source_policy import SourcePolicy
        policy = SourcePolicy()
        return DownloadService(
            policy=policy, session=make_session(policy), max_bytes=self.settings.max_download_bytes,
            connect_timeout=self.settings.connect_timeout, read_timeout=self.settings.read_timeout,
        )

    def _ask_existing(self, path: Path) -> Optional[tuple[str, bool]]:
        """Pergunta o que fazer com um destino já existente. Devolve (nome_sem_ext, overwrite) ou None."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Arquivo já existe")
        box.setText(f"“{path.name}” já existe na pasta de destino.")
        replace = box.addButton("Substituir", QMessageBox.DestructiveRole)
        rename = box.addButton("Salvar com novo nome", QMessageBox.AcceptRole)
        box.addButton("Cancelar", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace:
            return path.stem, True
        if clicked is rename:
            return unique_path(path).stem, False
        return None

    def _start(self) -> None:
        dest_dir = Path(self.dir_edit.text().strip()).expanduser()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._set_msg(f"Não foi possível usar a pasta de destino: {exc}", error=True)
            return
        if self.remote is not None:
            self._start_remote(dest_dir)
        else:
            for path in self.local_files:
                self._queue_convert(path, dest_dir, self.name_edit.text().strip() or path.stem, self._current_options())

    def _queue_convert(self, src: Path, dest_dir: Path, name: str, opts: Optional[ConversionOptions], delete_source_on_success: bool = False) -> None:
        if opts is None or self.tools is None:
            return
        out = MediaService.resolve_output(src, dest_dir, name, opts.fmt)
        overwrite = False
        if out.exists():
            choice = self._ask_existing(out)
            if choice is None:
                return
            name, overwrite = choice
        kind = TaskKind.EXTRACT_AUDIO if opts.mode == MODE_AUDIO and src.suffix.lower() in VIDEO_EXTENSIONS else TaskKind.CONVERT
        task = Task(kind=kind, title=src.name, output_format=opts.fmt.key.upper())
        service = MediaService(self.tools)

        def job(t: Task, report):
            output = service.convert(src, dest_dir, name, opts, report, t.cancel_event, overwrite)
            if delete_source_on_success:
                try:
                    source = Path(src).resolve()
                    converted = Path(output).resolve()
                    if source != converted:
                        source.unlink(missing_ok=True)
                except OSError as exc:
                    logging.getLogger(__name__).warning(
                        'Conversao concluida, mas nao foi possivel remover o original %s: %s',
                        src, exc,
                    )
            return output

        self._submit(task, job)

    def _start_remote(self, dest_dir: Path) -> None:
        assert self.remote is not None and self.remote_url

        convert = self.chk_convert.isChecked()
        service = self._download_service()
        url, remote = self.remote_url, self.remote

        # Audio do YouTube: baixa somente o fluxo de audio.
        audio_only = remote.is_youtube and self._mode() == MODE_AUDIO
        opts = self._current_options() if (convert or audio_only) else None

        if audio_only and opts is None:
            self._set_msg("Selecione um formato de audio valido.", error=True)
            return

        wanted = self.name_edit.text().strip()

        if audio_only:
            audio_stem = Path(
                sanitize_filename(wanted or Path(remote.filename).stem)
            ).stem
            filename = audio_stem + opts.fmt.extension
        else:
            ext = Path(remote.filename).suffix
            filename = (
                remote.filename
                if convert or not wanted
                else sanitize_filename(wanted) + ext
            )

        target = dest_dir / sanitize_filename(filename)
        overwrite = False

        if target.exists():
            choice = self._ask_existing(target)
            if choice is None:
                return
            stem, overwrite = choice
            filename = stem + target.suffix

        task = Task(
            kind=TaskKind.EXTRACT_AUDIO if audio_only else TaskKind.DOWNLOAD,
            title=filename,
            output_format=Path(filename).suffix.lstrip(".").upper(),
            source_host=remote.host,
        )

        def job(t: Task, report):
            if remote.is_youtube:
                if audio_only and opts:
                    return service.download_youtube(
                        url,
                        dest_dir,
                        filename,
                        overwrite,
                        report,
                        t.cancel_event,
                        audio_format=opts.fmt.key,
                        audio_bitrate=opts.audio_bitrate,
                    )

                return service.download_youtube(
                    url, dest_dir, filename, overwrite, report, t.cancel_event
                )

            return service.download(
                url, dest_dir, filename, overwrite, report, t.cancel_event
            )

        # A extracao de audio ja acontece dentro do download.
        # Somente o modo Video usa a conversao posterior.
        if convert and opts and not audio_only:
            final_name = wanted or Path(remote.filename).stem
            task.followup = lambda done, o=opts, n=final_name, d=dest_dir: (
                self._queue_convert(
                    done.output_path, d, n, o, delete_source_on_success=True
                )
            )

        self._submit(task, job)

    def _submit(self, task: Task, job) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._rows[task.id] = row
        self.current_task_id = task.id
        self.tasks.submit(task, job)

    # ================================================================== atualização de tarefas
    @Slot(object)
    def _on_task_changed(self, task: Task) -> None:
        row = self._rows.get(task.id)
        if row is not None:
            pct = "—" if task.progress is None else f"{task.progress * 100:.0f}%"
            for col, text in enumerate([task.title, task.kind.label, task.status.label, pct, task.message]):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(text)
                item.setData(Qt.UserRole, task.id)
        if task.id == self.current_task_id:
            self._update_footer(task)
        if task.status is TaskStatus.COMPLETED:
            self.last_output = task.output_path
            if task.followup and not task.followup_done:
                task.followup_done = True
                self.current_task_id = task.id
                task.followup(task)
            if task.kind is TaskKind.DOWNLOAD and task.output_path:
                self._load_downloaded_preview(task.output_path)
        if task.status.is_final:
            self.btn_cancel.setEnabled(bool(self.tasks.active_tasks()))

    def _update_footer(self, task: Task) -> None:
        if task.progress is None and task.status is TaskStatus.RUNNING:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int((task.progress or 0) * 1000))
            self.progress.setFormat(f"{(task.progress or 0) * 100:.0f}%")
        color = {TaskStatus.FAILED: DANGER, TaskStatus.COMPLETED: OK}.get(task.status, MUTED)
        detail = f" — {task.message}" if task.message and task.status.is_final else ""
        self.state_label.setText(f"<span style='color:{color}'><b>{task.status.label}</b></span>: {task.title}{detail}")
        self.speed_label.setText(f"Velocidade: {human_speed(task.speed_bps)}" if task.speed_bps else "")
        self.eta_label.setText(f"Restante: {human_duration(task.eta_seconds)}" if task.eta_seconds else "")
        self.btn_cancel.setEnabled(not task.status.is_final)
        done = task.status is TaskStatus.COMPLETED and task.output_path is not None
        self.btn_open.setEnabled(done)
        self.btn_show.setEnabled(done)

    def _on_row_selected(self) -> None:
        items = self.table.selectedItems()
        if items:
            task = self.tasks.get(items[0].data(Qt.UserRole))
            if task:
                self.current_task_id = task.id
                self._update_footer(task)

    def _record_history(self, task: Task) -> None:  # thread de trabalho
        try:
            self.history.add_task(task)
        except Exception:  # histórico nunca deve derrubar uma tarefa
            pass

    def _load_downloaded_preview(self, path: Path) -> None:
        if self.tools is None:
            return
        tools, tmp = self.tools, Path(self._tmp.name)

        def work():
            info = probe(path, tools)
            thumb = None
            if info.has_video:
                out = tmp / f"thumb_{int(time.time() * 1000)}.png"
                at = min(1.0, (info.duration or 0) / 2)
                if MediaService(tools).make_thumbnail(path, out, at):
                    thumb = out
            return info, thumb

        def done(result):
            if self.last_output == path and self.remote is not None and not self.local_files:
                info, thumb = result
                self._apply_local_info(info, thumb)
                self._set_msg("Download concluído; metadados e miniatura processados localmente.", ok=True)

        self._run_async(work, done, lambda msg: self._set_msg(msg, error=True))

    # ================================================================== ações
    def _cancel(self) -> None:
        task = self.tasks.get(self.current_task_id) if self.current_task_id else None
        if task and not task.status.is_final:
            self.tasks.cancel(task.id)
        else:
            self.tasks.cancel_all()

    def _open_folder(self) -> None:
        folder = self.last_output.parent if self.last_output else Path(self.dir_edit.text())
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _show_file(self) -> None:
        if not self.last_output:
            return
        path = str(self.last_output)
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", f"/select,{path}"])  # lista de argumentos, sem shell
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output.parent)))
        except OSError:
            self._open_folder()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.settings = Settings(**dlg.result_settings().__dict__)
            self.settings.save(self.settings_path)
            self.history.retention_days = self.settings.history_retention_days
            self.dir_edit.setText(self.settings.output_dir)
            self._refresh_tools()

    def _open_history(self) -> None:
        HistoryDialog(self.history, self).exec()

    def _set_msg(self, text: str, error: bool = False, ok: bool = False) -> None:
        color = DANGER if error else OK if ok else MUTED
        self.source_msg.setText(f"<span style='color:{color}'>{text}</span>")

    # ================================================================== encerramento
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.tasks.active_tasks():
            answer = QMessageBox.question(
                self, "Tarefas em andamento", "Há tarefas em andamento. Cancelar tudo e sair?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.tasks.shutdown()
        self._pool.waitForDone(2000)
        self._tmp.cleanup()
        event.accept()
