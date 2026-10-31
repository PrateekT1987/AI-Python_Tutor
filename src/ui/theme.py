"""Application-wide theme: palette and stylesheet for the desktop UI.

Supports:
- Dark (default)
- High Contrast (WCAG AA compliant)
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# ─── Dark Theme (default) ──────────────────────────────────────────────
DARK_COLORS = {
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

DARK_QSS = """
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

# ─── High Contrast Theme (WCAG AA) ─────────────────────────────────────
# Foreground/background ratios ≥ 4.5:1 for normal text, ≥ 3:1 for large
HIGH_CONTRAST_COLORS = {
    "bg": "#000000",        # pure black
    "panel": "#0A0A0A",     # near black
    "surface": "#1A1A1A",   # dark gray
    "border": "#FFFFFF",    # pure white
    "text": "#FFFFFF",      # pure white
    "text_muted": "#CCCCCC", # light gray (4.5:1 on black)
    "text_dim": "#AAAAAA",   # medium gray (3:1 on black)
    "accent": "#00FFFF",    # cyan (high contrast on black)
    "accent_hover": "#80FFFF", # light cyan
    "amber": "#FFFF00",     # yellow
    "danger": "#FF4444",    # bright red
}

HIGH_CONTRAST_QSS = """
QWidget { color: #FFFFFF; font-weight: 500; }
QMainWindow, QDialog { background-color: #000000; }
QLabel { background: transparent; color: #FFFFFF; }

QMenuBar { background-color: #0A0A0A; color: #FFFFFF; border-bottom: 2px solid #FFFFFF; }
QMenuBar::item { background: transparent; padding: 6px 12px; color: #FFFFFF; }
QMenuBar::item:selected { background: #1A1A1A; border: 1px solid #FFFFFF; }
QMenu { background: #0A0A0A; color: #FFFFFF; border: 2px solid #FFFFFF; padding: 4px; }
QMenu::item { padding: 8px 28px 8px 16px; border-radius: 0; color: #FFFFFF; }
QMenu::item:selected { background: #1A1A1A; border: 1px solid #00FFFF; }
QMenu::separator { height: 2px; background: #FFFFFF; margin: 4px 8px; }

QStatusBar { background: #0A0A0A; color: #CCCCCC; border-top: 2px solid #FFFFFF; }
QStatusBar::item { border: none; }

QToolTip { background: #000000; color: #FFFFFF; border: 2px solid #FFFFFF; padding: 6px; font-weight: bold; }

QTextEdit, QTextBrowser, QPlainTextEdit {
    background: #1A1A1A;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 4px;
    selection-background-color: #00FFFF;
    selection-color: #000000;
}
QLineEdit {
    background: #1A1A1A;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 4px;
    padding: 8px 12px;
    selection-background-color: #00FFFF;
    selection-color: #000000;
}
QLineEdit:focus { border-color: #00FFFF; }

QSpinBox, QDoubleSpinBox, QComboBox {
    background: #1A1A1A;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 28px;
}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #00FFFF; }
QComboBox QAbstractItemView {
    background: #0A0A0A;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    selection-background-color: #00FFFF;
    selection-color: #000000;
}

QCheckBox { color: #FFFFFF; spacing: 10px; font-weight: bold; }
QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #FFFFFF; background: #000000; }
QCheckBox::indicator:checked { background: #00FFFF; border-color: #00FFFF; }

QPushButton {
    background: #1A1A1A;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 4px;
    padding: 10px 18px;
    font-weight: bold;
}
QPushButton:hover { background: #003333; border-color: #00FFFF; }
QPushButton:pressed { background: #005555; }
QPushButton:disabled { color: #666666; background: #0A0A0A; border-color: #444444; }
QDialogButtonBox QPushButton { min-width: 100px; }

QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #FFFFFF;
    border-radius: 0;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover { background: #00FFFF; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 14px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #FFFFFF;
    border-radius: 0;
    min-width: 40px;
}
QScrollBar::handle:horizontal:hover { background: #00FFFF; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QAbstractScrollArea::corner { background: transparent; }
"""

# ─── Theme Registry ────────────────────────────────────────────────────
class Theme(Enum):
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"

THEME_SPECS = {
    Theme.DARK: (DARK_COLORS, DARK_QSS),
    Theme.HIGH_CONTRAST: (HIGH_CONTRAST_COLORS, HIGH_CONTRAST_QSS),
}

_current_theme = Theme.DARK


def get_current_theme() -> Theme:
    return _current_theme


def set_theme(app: QApplication, theme: Theme) -> None:
    """Apply a theme to the application."""
    global _current_theme
    _current_theme = theme
    colors, qss = THEME_SPECS[theme]
    _apply_palette(app, colors)
    app.setStyleSheet(qss)


def _apply_palette(app: QApplication, colors: dict) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(colors["danger"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["text_dim"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(colors["text_dim"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(colors["text_dim"]),
    )
    QApplication.instance().setPalette(palette)


# Backward compatibility
COLORS = DARK_COLORS
GLOBAL_QSS = DARK_QSS


def apply_theme(app: QApplication) -> None:
    """Apply the default dark theme (backward compatible)."""
    app.setStyle("Fusion")
    set_theme(app, Theme.DARK)