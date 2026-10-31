"""Application-wide theme: one palette and one stylesheet for the desktop UI."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

COLORS = {
    "bg": "#1E1E1E",
    "panel": "#252931",
    "surface": "#252526",
    "border": "#3A3F4B",
    "text": "#D9D6CB",
    "text_muted": "#8B93A1",
    "text_dim": "#7C8896",
    "accent": "#61AFEF",
    "accent_hover": "#78C0F0",
    "amber": "#E5C07B",
    "danger": "#C45A4A",
}

GLOBAL_QSS = """
QWidget { color: #D9D6CB; }
QMainWindow, QDialog { background-color: #1E1E1E; }
QLabel { background: transparent; }

QMenuBar { background-color: #252931; color: #ABB2BF; border-bottom: 1px solid #3A3F4B; }
QMenuBar::item { background: transparent; padding: 4px 10px; }
QMenuBar::item:selected { background: #3A3F4B; border-radius: 4px; }
QMenu { background: #252931; color: #ABB2BF; border: 1px solid #3A3F4B; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: #3A3F4B; }
QMenu::separator { height: 1px; background: #3A3F4B; margin: 4px 8px; }

QStatusBar { background: #252931; color: #8B93A1; border-top: 1px solid #3A3F4B; }
QStatusBar::item { border: none; }

QToolTip { background: #2D2D2D; color: #D9D6CB; border: 1px solid #3A3F4B; padding: 4px; }

QTextEdit, QTextBrowser, QPlainTextEdit {
    background: #252526;
    color: #D9D6CB;
    border: 1px solid #3A3F4B;
    border-radius: 6px;
    selection-background-color: #3A5F8A;
    selection-color: #FFFFFF;
}
QLineEdit {
    background: #252526;
    color: #E0E0E0;
    border: 1px solid #3A3F4B;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: #3A5F8A;
}
QLineEdit:focus { border-color: #61AFEF; }

QSpinBox, QDoubleSpinBox, QComboBox {
    background: #252526;
    color: #D9D6CB;
    border: 1px solid #3A3F4B;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #61AFEF; }
QComboBox QAbstractItemView {
    background: #252931;
    color: #D9D6CB;
    border: 1px solid #3A3F4B;
    selection-background-color: #3A3F4B;
}

QCheckBox { color: #ABB2BF; spacing: 8px; }

QPushButton {
    background: #2D3139;
    color: #D9D6CB;
    border: 1px solid #3A3F4B;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover { background: #3A3F4B; }
QPushButton:pressed { background: #252931; }
QPushButton:disabled { color: #7C8896; background: #2A2E36; border-color: #333842; }
QDialogButtonBox QPushButton { min-width: 80px; }

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3A3F4B;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #4A4F5B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3A3F4B;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #4A4F5B; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QAbstractScrollArea::corner { background: transparent; }
"""


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to the whole application."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2A2E38"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2D2D2D"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2D3139"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["danger"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_dim"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#6B7280"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor("#6B7280"),
    )
    app.setPalette(palette)
    app.setStyleSheet(GLOBAL_QSS)
