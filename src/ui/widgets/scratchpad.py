"""Scratchpad widget for free-form code experimentation."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.logging_setup import get_logger
from src.core.settings import config_dir
from src.ui.widgets.code_editor import CodeEditor

log = get_logger(__name__)


class ScratchpadWidget(QDialog):
    """Scratchpad for free-form code experimentation."""

    run_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scratchpad")
        self.setModal(False)
        self.resize(760, 620)
        self._setup_ui()
        self._load_content()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel("Scratchpad")
        title.setStyleSheet("font-weight: 600; font-size: 13px;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self.ask_btn = QPushButton("Ask Tutor (Ctrl+Enter)")
        self.ask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_btn.setAccessibleName("Ask the tutor about this code")
        self.ask_btn.clicked.connect(self._emit_run)
        toolbar.addWidget(self.ask_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setAccessibleName("Save scratchpad")
        self.save_btn.clicked.connect(self._save)
        toolbar.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setAccessibleName("Clear scratchpad")
        self.clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(self.clear_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.hide)
        toolbar.addWidget(self.close_btn)

        layout.addLayout(toolbar)

        # Editor
        self.editor = CodeEditor()
        self.editor.setPlaceholderText("Paste or write Python here, then ask the tutor about it…")
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #E6E6E6;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.editor, 1)

        # Status line
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8B93A1; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Syntax highlighting
        from src.ui.widgets.syntax_highlighter import PythonHighlighter
        self.highlighter = PythonHighlighter(self.editor.document())

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.editor)
        shortcut.activated.connect(self._emit_run)

    def _emit_run(self):
        code = self.editor.toPlainText().strip()
        if not code:
            self.status_label.setText("Nothing to ask — the scratchpad is empty.")
            return
        self.status_label.setText("Sent to the tutor.")
        self.run_requested.emit(code)

    def _scratch_path(self) -> Path:
        return config_dir() / "scratchpad.py"

    def _load_content(self):
        scratch_file = self._scratch_path()
        if scratch_file.exists():
            try:
                self.editor.setPlainText(scratch_file.read_text(encoding="utf-8"))
            except OSError:
                pass

    def _save(self):
        scratch_file = self._scratch_path()
        try:
            scratch_file.write_text(self.editor.toPlainText(), encoding="utf-8")
            self.status_label.setText(f"Saved to {scratch_file}")
        except OSError as exc:
            self.status_label.setText(f"Could not save: {exc}")

    def _clear(self):
        self.editor.clear()
        self.status_label.setText("Scratchpad cleared.")
        self._save()