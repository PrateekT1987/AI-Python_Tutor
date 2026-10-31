"""Input area with integrated Send/Stop buttons."""

from __future__ import annotations

import math

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QWidget


class ChatInput(QPlainTextEdit):
    """Multi-line input: Enter sends, Shift+Enter inserts a line break."""

    submit_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.submit_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class InputArea(QWidget):
    """Input area with integrated Send/Stop buttons."""

    send_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()

    MIN_HEIGHT = 42
    MAX_HEIGHT = 132

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Prompt label
        self.prompt_label = QLabel(">>>")
        self.prompt_label.setStyleSheet(
            "color: #E5C07B; font-family: 'JetBrains Mono', monospace; font-size: 13px;"
        )
        self.prompt_label.setAccessibleName("Prompt")
        layout.addWidget(self.prompt_label, 0, Qt.AlignmentFlag.AlignTop)

        # Input entry (multi-line so code and tracebacks can be pasted)
        self.input_entry = ChatInput()
        self.input_entry.setPlaceholderText(
            "Ask a question or paste code / an error message — Enter to send, Shift+Enter for a new line"
        )
        self.input_entry.setAccessibleName("Message input")
        self.input_entry.setTabChangesFocus(True)
        self.input_entry.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #2D3139;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
            }
            QPlainTextEdit:focus { border: 1px solid #61AFEF; }
        """)
        self.input_entry.setFixedHeight(self.MIN_HEIGHT)
        self.input_entry.document().setDocumentMargin(2)
        self.input_entry.submit_requested.connect(self._on_send)
        self.input_entry.textChanged.connect(self._update_height)
        layout.addWidget(self.input_entry, 1)

        # Send button
        self.run_btn = QPushButton("Send")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setAccessibleName("Send message")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #61AFEF;
                color: #1E1E1E;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-family: 'JetBrains Mono', monospace;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #78C0F0; }
            QPushButton:disabled { background-color: #3A3F4B; color: #7C8896; }
        """)
        self.run_btn.clicked.connect(self._on_send)
        layout.addWidget(self.run_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setAccessibleName("Stop generating")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #C45A4A;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-family: 'JetBrains Mono', monospace;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #D46A5A; }
            QPushButton:disabled { background-color: #3A3F4B; color: #7C8896; }
        """)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignBottom)

    def _update_height(self):
        layout = self.input_entry.document().documentLayout()
        # QPlainTextDocumentLayout reports the document height in wrapped
        # lines, not pixels.
        lines = max(1, round(layout.documentSize().height()))
        line_height = QFontMetrics(self.input_entry.font()).lineSpacing()
        height = int(min(max(lines * line_height + 24, self.MIN_HEIGHT), self.MAX_HEIGHT))
        if self.input_entry.height() != height:
            self.input_entry.setFixedHeight(height)

    def _on_send(self):
        text = self.input_entry.toPlainText().strip()
        if not text:
            return
        self.send_requested.emit(text)
        self.input_entry.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_height)

    def set_loading(self, loading: bool):
        self.run_btn.setEnabled(not loading)
        self.stop_btn.setEnabled(loading)
        self.input_entry.setEnabled(not loading)
        if loading:
            self.input_entry.setPlaceholderText("Thinking… (Stop to cancel)")
        else:
            self.input_entry.setPlaceholderText(
                "Ask a question or paste code / an error message — Enter to send, Shift+Enter for a new line"
            )
            self.input_entry.setFocus()

    def set_side_margins(self, side: int):
        """Align the composer with the centred transcript column."""
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(side, 12, side, 12)