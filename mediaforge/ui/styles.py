"""Tema escuro (grafite) com detalhes em ciano/azul."""

BG = "#1a1c20"
PANEL = "#23262c"
PANEL_ALT = "#2a2e35"
BORDER = "#363b44"
TEXT = "#e6e9ee"
MUTED = "#9aa3b0"
ACCENT = "#22c3e6"
ACCENT_DARK = "#1a9fbd"
BLUE = "#3b82f6"
DANGER = "#f0605d"
WARN = "#f5b84b"
OK = "#4cd08a"

STYLESHEET = f"""
* {{ font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#root, QScrollArea {{ background: {BG}; }}
QFrame#header {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#title {{ font-size: 20px; font-weight: 700; color: {ACCENT}; }}
QLabel#badge {{ color: {OK}; background: rgba(76,208,138,0.10); border: 1px solid rgba(76,208,138,0.35);
    border-radius: 10px; padding: 3px 10px; font-size: 12px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#banner {{ background: rgba(245,184,75,0.12); border: 1px solid {WARN}; border-radius: 8px; }}
QLabel#h2 {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#note {{ color: {WARN}; font-size: 12px; }}
QLabel#preview {{ background: {BG}; border: 1px dashed {BORDER}; border-radius: 8px; color: {MUTED}; }}
QLabel#infoKey {{ color: {MUTED}; }}
QLineEdit, QComboBox, QSpinBox, QTextBrowser {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 8px; selection-background-color: {ACCENT_DARK}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: #5d6672; background: #202329; }}
QComboBox QAbstractItemView {{ background: {PANEL_ALT}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_DARK};
    color: {TEXT}; }}
QComboBox QAbstractItemView::item:disabled {{ color: #5d6672; }}
QPushButton {{ background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #5d6672; background: #202329; border-color: #2c3037; }}
QPushButton#primary {{ background: {ACCENT_DARK}; border: 1px solid {ACCENT}; color: #04141a; font-weight: 700; padding: 10px 16px; }}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QPushButton#primary:disabled {{ background: #1d3a43; color: #4d7480; border-color: #24464f; }}
QPushButton#danger {{ border-color: {DANGER}; color: {DANGER}; }}
QPushButton#danger:disabled {{ border-color: #2c3037; color: #5d6672; }}
QPushButton#link {{ background: transparent; border: 1px solid {BLUE}; color: {BLUE}; }}
QPushButton#link:hover {{ background: rgba(59,130,246,0.15); }}
QRadioButton, QCheckBox {{ spacing: 8px; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #5d6672; background: {BG}; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:.5, cy:.5, radius:.5, fx:.5, fy:.5,
    stop:0 {ACCENT}, stop:0.55 {ACCENT}, stop:0.6 {BG}, stop:1 {BG}); border: 1px solid {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
QRadioButton:disabled, QCheckBox:disabled {{ color: #5d6672; }}
QProgressBar {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; text-align: center; min-height: 18px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BLUE}, stop:1 {ACCENT}); border-radius: 5px; }}
QTableWidget {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; gridline-color: {BORDER};
    alternate-background-color: #1f2227; }}
QHeaderView::section {{ background: {PANEL_ALT}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px; color: {MUTED}; }}
QTableWidget::item:selected {{ background: rgba(34,195,230,0.25); }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 24px; }}
QToolTip {{ background: {PANEL_ALT}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""
