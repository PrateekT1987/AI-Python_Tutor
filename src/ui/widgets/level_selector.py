"""Level selector segmented control."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class LevelSelector(QWidget):
    """Segmented control for difficulty level selection."""

    level_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_level = "Intermediate"
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.level_buttons = {}
        for level in ["Beginner", "Intermediate", "Advanced"]:
            btn = QPushButton(level)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setAccessibleName(f"{level} level")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2D2D2D;
                    color: #ABB2BF;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:checked { background-color: #61AFEF; color: #1E1E1F; }
                QPushButton:hover:!checked { background-color: #3A3A3A; }
            """)
            btn.toggled.connect(lambda checked, lvl=level: self._on_level_changed(lvl, checked))
            layout.addWidget(btn)
            self.level_buttons[level] = btn

        # Set initial state
        self.level_buttons[self.current_level].setChecked(True)

    def _on_level_changed(self, level: str, checked: bool):
        if checked:
            self.current_level = level
            for lvl, btn in self.level_buttons.items():
                if lvl != level:
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
            self.level_changed.emit(level)

    def set_level(self, level: str):
        """Set the selected level without emitting ``level_changed``."""
        if level not in self.level_buttons:
            return
        self.current_level = level
        for lvl, btn in self.level_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(lvl == level)
            btn.blockSignals(False)