"""Diálogos: configurações, histórico e ajuda."""
from __future__ import annotations
__author__ = "Ernani Salasar"
__copyright__ = "Copyright (c) 2026 Ernani Salasar"
__software__ = "MediaForge"


import time
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout,
)

from mediaforge import APP_NAME, __version__
from mediaforge.services.ffmpeg_locator import INSTALL_HELP
from mediaforge.services.source_policy import STUDIO_URL, TAKEOUT_URL
from mediaforge.storage.history import HistoryStore
from mediaforge.storage.settings import Settings
from mediaforge.utils import human_size


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(520)
        self._settings = settings
        form = QFormLayout()
        self.out_edit = QLineEdit(settings.output_dir)
        out_btn = QPushButton("Procurar…")
        out_btn.clicked.connect(lambda: self._browse(self.out_edit))
        form.addRow("Pasta de destino padrão", self._row(self.out_edit, out_btn))
        self.ff_edit = QLineEdit(settings.ffmpeg_dir)
        self.ff_edit.setPlaceholderText("Opcional: pasta 'bin' que contém ffmpeg e ffprobe")
        ff_btn = QPushButton("Procurar…")
        ff_btn.clicked.connect(lambda: self._browse(self.ff_edit))
        form.addRow("Pasta do FFmpeg", self._row(self.ff_edit, ff_btn))
        self.max_spin = self._spin(1, 102400, settings.max_download_mb, " MB")
        form.addRow("Limite por download", self.max_spin)
        self.ret_spin = self._spin(0, 3650, settings.history_retention_days, " dias")
        self.ret_spin.setToolTip("0 = manter o histórico indefinidamente")
        form.addRow("Retenção do histórico", self.ret_spin)
        self.ct_spin = self._spin(3, 120, settings.connect_timeout, " s")
        form.addRow("Timeout de conexão", self.ct_spin)
        self.rt_spin = self._spin(5, 600, settings.read_timeout, " s")
        form.addRow("Timeout de leitura", self.rt_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(lo, hi, value, suffix):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        s.setSuffix(suffix)
        return s

    @staticmethod
    def _row(edit, button):
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit, 1)
        h.addWidget(button)
        return w

    def _browse(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta", edit.text())
        if folder:
            edit.setText(folder)

    def result_settings(self) -> Settings:
        return replace(
            self._settings,
            output_dir=self.out_edit.text().strip(),
            ffmpeg_dir=self.ff_edit.text().strip(),
            max_download_mb=self.max_spin.value(),
            history_retention_days=self.ret_spin.value(),
            connect_timeout=self.ct_spin.value(),
            read_timeout=self.rt_spin.value(),
        )


class HistoryDialog(QDialog):
    HEADERS = ["Data", "Operação", "Arquivo", "Formato", "Estado", "Tamanho", "Servidor de origem"]

    def __init__(self, history: HistoryStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico (armazenado somente neste computador)")
        self.resize(900, 460)
        self.history = history
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        clear_btn = QPushButton("Limpar histórico")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton("Fechar")
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addWidget(clear_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(row)
        self.reload()

    def reload(self) -> None:
        entries = self.history.list()
        self.table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            values = [
                time.strftime("%d/%m/%Y %H:%M", time.localtime(e.finished_at)), e.operation, e.file_name,
                e.output_format, e.status, human_size(e.size_bytes) if e.size_bytes else "—", e.source_host or "local",
            ]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                if c == 2 and e.message:
                    item.setToolTip(e.message)
                self.table.setItem(r, c, item)

    def _clear(self) -> None:
        if QMessageBox.question(self, "Limpar histórico", "Apagar todo o histórico deste computador?") == QMessageBox.Yes:
            self.history.clear()
            self.reload()


HELP_HTML = f"""
<!-- MediaForge | Autor: Ernani Salasar | Copyright 2026 -->
<h2>MediaForge — Central de ajuda</h2>
<p><b>Versão:</b> {__version__}</p>
<p>Guia de uso do MediaForge para baixar mídia autorizada, preservar a qualidade original, converter vídeos e extrair áudio.</p>
<hr>

<h3>1. Como baixar um vídeo ou áudio</h3>
<ol>
<li>Cole no campo <b>Fonte e informações</b> um link direto de mídia ou o endereço de um vídeo individual público do YouTube.</li>
<li>Clique em <b>Validar fonte</b> e aguarde o carregamento das informações.</li>
<li>Escolha <b>Vídeo</b> ou <b>Áudio</b>, confira a qualidade e defina a pasta de destino.</li>
<li>Se quiser apenas baixar o arquivo original, deixe desmarcada a opção de conversão e clique em <b>Baixar</b>.</li>
<li>Acompanhe o andamento na <b>Fila de tarefas</b>. Ao terminar, use os comandos para abrir o arquivo ou a pasta de destino.</li>
</ol>

<h3>2. Qualidade e resolução</h3>
<ul>
<li><b>Original:</b> procura preservar a melhor qualidade disponível na fonte. A resolução máxima depende dos formatos que o serviço disponibiliza.</li>
<li><b>Resolução específica:</b> permite escolher um limite de resolução quando essa opção estiver disponível. Não aumenta a qualidade real da fonte.</li>
<li><b>Qualidade do áudio:</b> define a qualidade de saída da conversão. Uma taxa de bits maior não recupera detalhes que não existem no áudio original.</li>
</ul>
<p><b>Dica:</b> se o objetivo é baixar rapidamente em 1080p, 1440p ou 4K, prefira <b>Original</b> e deixe a conversão desmarcada. A qualidade máxima só será possível quando a fonte realmente oferecer esse formato.</p>

<h3>3. Quando usar a conversão</h3>
<p>Marque <b>Converter para o formato escolhido após baixar</b> apenas quando precisar de um formato específico, como MP4.</p>
<ul>
<li><b>Desmarcada:</b> o download mantém o formato disponibilizado pela fonte, sem a etapa adicional de conversão.</li>
<li><b>Marcada:</b> o aplicativo baixa o arquivo e depois o converte para o formato escolhido. A fila pode mostrar uma tarefa de download e outra de conversão; são etapas diferentes do mesmo trabalho.</li>
<li><b>Tempo de conversão:</b> depende da resolução, dos codecs, da duração e do desempenho do computador. Converter um vídeo 4K, especialmente de AV1 para H.264, pode demorar bastante.</li>
<li><b>Cancelamento:</b> se a conversão for cancelada ou falhar, o arquivo original baixado deve ser preservado para permitir uma nova tentativa.</li>
</ul>
<p>Os formatos disponíveis incluem MP4 (H.264 + AAC), WebM (VP9 + Opus), MOV e MKV. A compatibilidade pode variar conforme o dispositivo e o editor utilizado.</p>

<h3>4. Trabalhar com arquivos locais</h3>
<ol>
<li>Clique em <b>Selecionar arquivos</b> ou arraste arquivos para a área indicada.</li>
<li>Escolha Vídeo ou Áudio, o formato de saída, a qualidade e a pasta de destino.</li>
<li>Clique em <b>Converter</b> e acompanhe a fila até a conclusão.</li>
</ol>
<p>O arquivo original não deve ser sobrescrito durante a conversão. Confira o destino escolhido antes de iniciar operações em lote.</p>

<h3>5. Fontes do YouTube</h3>
  <p>A extração é feita pelo <b>yt-dlp</b>. No modo Áudio, o aplicativo solicita somente o melhor fluxo de áudio e usa o FFmpeg para gerar o formato escolhido. São suportados vídeos individuais públicos; playlists, transmissões ao vivo e conteúdo privado ou sujeito a restrições podem não funcionar.</p>
<p>Para exportar conteúdo da sua própria conta, utilize o <a href="{STUDIO_URL}">YouTube Studio</a> ou o <a href="{TAKEOUT_URL}">Google Takeout</a>.</p>

<h3>6. Solução de problemas</h3>
<p><b>FFmpeg ou FFprobe não encontrados:</b> no PowerShell, execute:</p>
<pre>winget install Gyan.FFmpeg</pre>
<p>Depois feche e reabra o terminal e o MediaForge. Confira a instalação com:</p>
<pre>ffmpeg -version
ffprobe -version</pre>
<p>Se necessário, configure o caminho dos executáveis em <b>Configurações</b>.</p>

<p><b>O vídeo não pode ser validado:</b> confirme que a URL está correta, que o vídeo está acessível publicamente e que não é uma playlist ou transmissão ao vivo.</p>
<p><b>Formato indisponível:</b> nem todas as fontes oferecem os mesmos codecs ou resoluções. Tente a opção Original ou outro formato compatível.</p>
<p><b>Conversão lenta:</b> isso é normal em arquivos grandes ou 4K. Se não precisar mudar o formato, desative a conversão e mantenha o arquivo original.</p>

<h3>7. Privacidade e segurança</h3>
<ul>
<li>O processamento dos arquivos locais é realizado no computador.</li>
<li>Não forneça senhas, cookies de navegador ou credenciais para tentar contornar restrições de acesso.</li>
<li>O aplicativo bloqueia endereços de rede local e outros destinos restritos pela política de segurança.</li>
<li>O histórico registra informações da operação, não a URL completa da fonte.</li>
</ul>

<p>Baixe ou converta somente conteúdo que você criou, que esteja em domínio público, sob licença permitida ou para o qual tenha autorização. Respeite os direitos autorais, os termos dos serviços e a legislação aplicável.</p>

<hr>
<p><b>Desenvolvido por Ernani Salasar</b></p>
<p><small>Copyright (c) 2026 Ernani Salasar.</small></p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuda")
        self.resize(680, 620)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(HELP_HTML)
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(close, alignment=Qt.AlignRight)
