"""Main application window for Python Tutor."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.logging_setup import get_logger
from src.core.settings import clear_session, fit_messages, load_session, save_session
from src.core.workers import ConnectionTestThread, LLMThread
from src.prompts import STARTERS, build_system_prompt
from src.ui.widgets import InputArea, LevelSelector, MessageBubble, ScratchpadWidget

log = get_logger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog for the API key, model and generation parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(480, 380)
        self._config = None
        self._test_thread: ConnectionTestThread | None = None
        self._testing = False
        self.buttons: QDialogButtonBox | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("sk-or-… (leave empty for local endpoints)")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setAccessibleName("OpenRouter API key")
        self.show_key_check = QCheckBox("Show")
        self.show_key_check.setAccessibleName("Show API key")
        self.show_key_check.toggled.connect(self._toggle_key_visibility)
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.show_key_check)
        form.addRow("API key:", key_row)

        test_row = QHBoxLayout()
        test_row.setSpacing(10)
        self.test_btn = QPushButton("Test connection")
        self.test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_btn)
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        self.test_status.setStyleSheet("color: #8B93A1; font-size: 11px;")
        test_row.addWidget(self.test_status, 1)
        form.addRow("", test_row)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("e.g., nvidia/nemotron-3-ultra-550b-a55b:free")
        form.addRow("Model ID:", self.model_edit)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setDecimals(1)
        form.addRow("Temperature:", self.temp_spin)

        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(64, 8192)
        self.tokens_spin.setSingleStep(128)
        form.addRow("Max Tokens:", self.tokens_spin)

        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(64, 4096)
        self.memory_spin.setSingleStep(64)
        self.memory_spin.setSuffix(" MB")
        self.memory_spin.setToolTip(
            "Saved for a future sandbox runner; code execution is not enabled yet."
        )
        form.addRow("Sandbox Memory:", self.memory_spin)

        self.network_check = QCheckBox("Allow Network in Sandbox")
        self.network_check.setToolTip(
            "Saved for a future sandbox runner; code execution is not enabled yet."
        )
        form.addRow(self.network_check)

        layout.addLayout(form)

        hint = QLabel("Settings are stored in the per-user config directory.")
        hint.setStyleSheet("color: #7C8896; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.buttons = buttons
        layout.addWidget(buttons)

    def closeEvent(self, event):
        # Never destroy the dialog while a test is in flight.
        if self._testing:
            self.test_status.setText("Waiting for the connection test to finish…")
            event.ignore()
            return
        super().closeEvent(event)

    def _toggle_key_visibility(self, visible: bool):
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.api_key_edit.setEchoMode(mode)

    def _test_connection(self):
        if self._testing:
            return
        self._testing = True
        self.test_btn.setEnabled(False)
        if self.buttons is not None:
            self.buttons.setEnabled(False)
        self.test_status.setText("Testing…")
        base_url = self._config.openrouter_base_url if self._config else "https://openrouter.ai/api/v1"
        self._test_thread = ConnectionTestThread(base_url, self.api_key_edit.text().strip())
        self._test_thread.result.connect(self._on_test_result)
        self._test_thread.finished.connect(self._test_thread.deleteLater)
        self._test_thread.start()

    @pyqtSlot(bool, str)
    def _on_test_result(self, ok: bool, message: str):
        self._testing = False
        self.test_btn.setEnabled(True)
        if self.buttons is not None:
            self.buttons.setEnabled(True)
        color = "#98C379" if ok else "#C45A4A"
        self.test_status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.test_status.setText(message)

    def load_settings(self, config):
        self._config = config
        self.api_key_edit.setText(config.openrouter_api_key)
        self.model_edit.setText(config.model)
        self.temp_spin.setValue(config.temperature)
        self.tokens_spin.setValue(config.max_tokens)
        self.memory_spin.setValue(config.sandbox_memory_mb)
        self.network_check.setChecked(config.sandbox_allow_network)

    def apply_settings(self, config):
        config.openrouter_api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip()
        if model:
            config.model = model
        config.temperature = self.temp_spin.value()
        config.max_tokens = self.tokens_spin.value()
        config.sandbox_memory_mb = self.memory_spin.value()
        config.sandbox_allow_network = self.network_check.isChecked()


class MainWindow(QMainWindow):
    """Main application window for Python Tutor."""

    # Chat column max width as a fraction of viewport (like Discord/ChatGPT).
    # Capped at an absolute maximum so ultra-wide screens don't stretch it.
    COLUMN_MAX_FRACTION = 0.90  # <-- Changed from 0.75 to 0.90 (90%)
    COLUMN_ABSOLUTE_MAX = 1400  # <-- Changed from 900 to 1400 (allows it to grow)
    MIN_MARGIN = 20
    ZOOM_MIN = -3
    ZOOM_MAX = 6

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.history: list[dict] = []
        self.scratchpad: ScratchpadWidget | None = None
        self.llm_thread: LLMThread | None = None
        self._threads: set[LLMThread] = set()

        self._bubbles: list[MessageBubble] = []
        self._message_rows: list[QWidget] = []
        self._assistant_bubble: MessageBubble | None = None
        self._last_error_bubble: MessageBubble | None = None
        self._last_partial_bubble: MessageBubble | None = None
        self._stream_buffer = ""
        self._request_active = False
        self._zoom = 0
        self._closing = False
        self._close_deadline = 0.0

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(66)
        self._stream_timer.timeout.connect(self._flush_stream)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._refit_bubbles)

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._restore_state()
        self.level_selector.set_level(self.config.level)
        self._apply_column_layout()
        self._load_history()
        self.input_area.input_entry.setFocus()

    # -- construction ----------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle("Python Tutor")
        self.setMinimumSize(860, 620)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_header())

        # Chat scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(0)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.chat_widget = QWidget()
        self.chat_widget.setStyleSheet("background-color: #1E1E1E;")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.setSpacing(14)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.chat_widget)

        # Starter questions (kept as a persistent widget)
        self.starters_widget = QWidget()
        self.starters_widget.setStyleSheet("background: transparent;")
        self.starters_layout = QVBoxLayout(self.starters_widget)
        self.starters_layout.setContentsMargins(0, 0, 0, 0)
        self.starters_layout.setSpacing(8)
        self._build_starters()

        # Transcript grows from the top; a single trailing stretch absorbs
        # the remaining viewport space.
        self.chat_layout.addWidget(self.starters_widget)
        self.chat_layout.addStretch(1)

        self.input_area = InputArea()
        self.input_area.send_requested.connect(self._on_send)
        self.input_area.stop_requested.connect(self._on_stop)

        main_layout.addWidget(self.scroll_area, 1)
        main_layout.addWidget(self.input_area)

        # Create the status bar up front so the window does not resize when
        # the first status message appears.
        self.statusBar().setSizeGripEnabled(False)

    def _create_header(self):
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(
            "background-color: #252931; border-bottom: 1px solid #3A3F4B;"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        title = QLabel("Python Tutor")
        title.setStyleSheet("color: #D9D6CB; font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel("Interactive Python Tutor")
        subtitle.setStyleSheet("color: #8B93A1; font-size: 11px;")
        layout.addWidget(subtitle)
        layout.addStretch()

        self.level_selector = LevelSelector()
        self.level_selector.level_changed.connect(self._on_level_changed)
        layout.addWidget(self.level_selector)

        self.scratch_btn = QPushButton("Scratchpad")
        self.scratch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scratch_btn.setAccessibleName("Toggle scratchpad")
        self.scratch_btn.setToolTip("Open the scratchpad (Ctrl+Shift+S)")
        self.scratch_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8B93A1;
                border: none;
                padding: 6px 10px;
                font-size: 11px;
                font-family: 'JetBrains Mono', monospace;
            }
            QPushButton:hover { color: #D9D6CB; background: #2D3139; border-radius: 4px; }
        """)
        self.scratch_btn.clicked.connect(self._toggle_scratchpad)
        layout.addWidget(self.scratch_btn)

        return header

    def _build_starters(self):
        label = QLabel("Ask anything — a concept, an error message, or code you want reviewed.")
        label.setStyleSheet("color: #8B93A1; font-size: 11px;")
        label.setWordWrap(True)
        self.starters_layout.addWidget(label)

        for starter in STARTERS[self.config.level]:
            btn = QPushButton(starter)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAccessibleName(starter)
            btn.setStyleSheet("""
                QPushButton {
                    background: #252931;
                    color: #D9D6CB;
                    border: 1px solid #3A3F4B;
                    border-left: 3px solid #E5C07B;
                    border-radius: 4px;
                    padding: 10px 12px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 13px;
                    text-align: left;
                }
                QPushButton:hover { background: #2D3139; border-color: #E5C07B; }
            """)
            btn.clicked.connect(lambda checked, s=starter: self._on_starter_clicked(s))
            self.starters_layout.addWidget(btn)

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Session", self)
        new_action.setShortcuts([QKeySequence.StandardKey.New, QKeySequence("Ctrl+L")])
        new_action.triggered.connect(self.new_session)
        file_menu.addAction(new_action)

        export_action = QAction("&Export Transcript...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_transcript)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("&Edit")
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        edit_menu.addAction(settings_action)

        view_menu = menubar.addMenu("&View")
        scratch_action = QAction("Toggle &Scratchpad", self)
        scratch_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        scratch_action.triggered.connect(self._toggle_scratchpad)
        view_menu.addAction(scratch_action)

        view_menu.addSeparator()

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self):
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.activated.connect(self._on_escape)

    # -- transcript ------------------------------------------------------

    def _add_message(
        self,
        role: str,
        content: str,
        animate: bool = True,
        retryable: bool = False,
        streaming: bool = False,
        scroll: bool = True,
    ) -> MessageBubble:
        bubble = MessageBubble(
            role,
            content,
            retryable=retryable,
            streaming=streaming,
        )
        bubble.ask_requested.connect(self._open_scratchpad_with_code)
        bubble.retry_requested.connect(self._retry_last)
        bubble.status_message.connect(self.set_status)
        bubble.output_updated.connect(self._on_output_updated)
        bubble.apply_zoom(self._zoom)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
        else:
            row_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addStretch(1)

        # Keep the trailing stretch last.
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row)
        self._message_rows.append(row)
        self._bubbles.append(bubble)
        self._fit_bubble(bubble)
        if scroll:
            self._scroll_to_bottom(force=animate)
        return bubble

    def _fit_bubble(self, bubble: MessageBubble):
        bubble.fit_width(self._available_chat_width())

    def _column_side_margin(self) -> int:
        viewport = self.scroll_area.viewport().width()
        column_width = min(
            int(viewport * self.COLUMN_MAX_FRACTION),
            self.COLUMN_ABSOLUTE_MAX,
        )
        return max(self.MIN_MARGIN, (viewport - column_width) // 2)

    def _available_chat_width(self) -> int:
        viewport = self.scroll_area.viewport().width()
        column_width = min(
            int(viewport * self.COLUMN_MAX_FRACTION),
            self.COLUMN_ABSOLUTE_MAX,
        )
        return max(MessageBubble.MIN_WIDTH, min(column_width, viewport - 2 * self.MIN_MARGIN))

    def _apply_column_layout(self):
        """Centre a readable column instead of stretching text to 4K edges."""
        side = self._column_side_margin()
        current = self.chat_layout.contentsMargins()
        if current.left() != side or current.right() != side:
            self.chat_layout.setContentsMargins(side, 20, side, 20)
        self.input_area.set_side_margins(side)

    def _refit_bubbles(self):
        self._apply_column_layout()
        for bubble in list(self._bubbles):
            self._fit_bubble(bubble)

    def _remove_bubble(self, bubble: MessageBubble | None):
        if bubble is None:
            return
        row = bubble.parentWidget()
        if row in self._message_rows:
            self._message_rows.remove(row)
            self.chat_layout.removeWidget(row)
            row.deleteLater()
        if bubble in self._bubbles:
            self._bubbles.remove(bubble)

    def _clear_messages(self):
        for bubble in self._bubbles:
            bubble.shutdown_runs()
        for row in self._message_rows:
            self.chat_layout.removeWidget(row)
            row.deleteLater()
        self._message_rows.clear()
        self._bubbles.clear()
        self._assistant_bubble = None
        self._last_error_bubble = None
        self._last_partial_bubble = None

    def _load_history(self):
        self.history = load_session()
        if not self.history:
            return
        self.starters_widget.hide()
        for message in self.history:
            self._add_message(
                message["role"],
                message["content"],
                animate=False,
                scroll=False,
            )
        self._scroll_to_bottom(force=True)

    def _scroll_to_bottom(self, force: bool = False):
        bar = self.scroll_area.verticalScrollBar()
        if force or bar.value() >= bar.maximum() - 140:
            QTimer.singleShot(30, lambda: bar.setValue(bar.maximum()))

    def _on_starter_clicked(self, starter: str):
        self._on_send(starter)

    def _on_level_changed(self, level: str):
        self.config.level = level
        self.config.save()
        self._rebuild_starters()
        self.set_status(f"Level set to {level}")

    def _rebuild_starters(self):
        while self.starters_layout.count():
            item = self.starters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._build_starters()

    # -- requests --------------------------------------------------------

    def _is_busy(self) -> bool:
        return self._request_active

    def _on_send(self, text: str | None = None):
        if self._is_busy():
            log.warning("Send attempted while busy")
            self.set_status("Please wait for the current answer (or press Stop).")
            return

        if text is None:
            text = self.input_area.input_entry.toPlainText().strip()
        text = text.strip()
        if not text:
            return

        if not self.config.openrouter_api_key:
            log.warning("Send attempted without API key")
            self.set_status("No API key configured — open Settings (Ctrl+,) if the request fails.")

        log.info("User message sent", chars=len(text), preview=text[:80])
        self.starters_widget.hide()
        self.history.append({"role": "user", "content": text})
        self._add_message("user", text)
        save_session(self.history)
        self._start_request()

    def _start_request(self):
        messages = [{"role": "system", "content": build_system_prompt(self.config.level)}]
        messages.extend(self.history)
        messages = fit_messages(messages)

        self._stream_buffer = ""
        self._last_error_bubble = None
        self._last_partial_bubble = None
        self._assistant_bubble = self._add_message("assistant", "", streaming=True)
        self.input_area.set_loading(True)
        self.set_status("Waiting for the tutor…")

        self._request_active = True
        thread = LLMThread(
            messages=messages,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        thread.token_received.connect(self._on_token)
        thread.status.connect(self.set_status)
        thread.answer_finished.connect(self._on_finished)
        thread.error.connect(self._on_error)
        thread.cancelled.connect(self._on_cancelled)
        thread.finished.connect(self._on_thread_finished)
        self.llm_thread = thread
        self._threads.add(thread)
        log.info("LLM request started", model=self.config.model, history_len=len(self.history))
        thread.start()

    @pyqtSlot(str)
    def _on_token(self, token: str):
        self._stream_buffer += token
        if not self._stream_timer.isActive():
            self._stream_timer.start()

    @pyqtSlot()
    def _flush_stream(self):
        if self._assistant_bubble is None:
            self._stream_timer.stop()
            return
        if self._stream_buffer:
            self._assistant_bubble.set_streaming_text(self._stream_buffer)
            self._maybe_scroll()

    def _maybe_scroll(self):
        bar = self.scroll_area.verticalScrollBar()
        if bar.value() >= bar.maximum() - 140:
            bar.setValue(bar.maximum())

    def _on_output_updated(self):
        # The bubble grows asynchronously, so scroll after layout settles.
        QTimer.singleShot(60, self._maybe_scroll)

    def _finish_assistant_bubble(self, text: str):
        self._stream_timer.stop()
        bubble = self._assistant_bubble
        if bubble is None:
            if text.strip():
                bubble = self._add_message("assistant", text, scroll=False)
            else:
                return
        if text.strip():
            bubble.set_content(text)
            self._fit_bubble(bubble)
        else:
            self._remove_bubble(bubble)
        self._assistant_bubble = None

    @pyqtSlot(str, bool)
    def _on_finished(self, text: str, truncated: bool):
        self._request_active = False
        self.input_area.set_loading(False)
        self._stream_timer.stop()

        if text.strip():
            self.history.append({"role": "assistant", "content": text})
            save_session(self.history)
            self._finish_assistant_bubble(text)
            log.info("LLM response finished", chars=len(text), truncated=truncated)
            self.set_status(
                "Answer reached the token limit — continue the conversation for more."
                if truncated else "Ready"
            )
        else:
            log.warning("LLM returned empty response")
            self._finish_assistant_bubble("")
            self.set_status("The model returned an empty response.")

        self._scroll_to_bottom(force=True)

    @pyqtSlot(str)
    def _on_error(self, error: str):
        self._request_active = False
        self.input_area.set_loading(False)
        self._stream_timer.stop()

        partial = self._stream_buffer
        if partial.strip():
            # Show what arrived, but do not persist a failed answer: keeping
            # the user turn last lets Retry re-ask cleanly.
            self._last_partial_bubble = self._assistant_bubble
            self._finish_assistant_bubble(partial)
        else:
            self._last_partial_bubble = None
            self._finish_assistant_bubble("")

        can_retry = any(m["role"] == "user" for m in self.history)
        message = f"**Request failed:** {error}"
        if can_retry:
            message += "\n\nUse **Retry** above to try again."

        bubble = self._add_message("assistant", message, retryable=can_retry)
        self._last_error_bubble = bubble
        log.error("LLM request failed", error=error, can_retry=can_retry)
        self.set_status("Request failed")
        if "OPENROUTER_API_KEY" in error or "authentication" in error.lower():
            self.set_status("Authentication failed — set your API key in Settings (Ctrl+,)")

    @pyqtSlot()
    def _on_cancelled(self):
        self._request_active = False
        self.input_area.set_loading(False)
        self._stream_timer.stop()

        partial = self._stream_buffer
        if partial.strip():
            self.history.append({"role": "assistant", "content": partial})
            save_session(self.history)
            self._finish_assistant_bubble(partial)
            log.info("LLM stream cancelled, partial saved", chars=len(partial))
        else:
            self._finish_assistant_bubble("")
            self._add_message("assistant", "*(stopped)*", scroll=False)
            log.info("LLM stream cancelled, no partial content")
        self.set_status("Stopped")
        self._scroll_to_bottom(force=True)

    def _on_stop(self):
        if self._request_active and self.llm_thread is not None:
            log.info("Stop requested by user")
            self.llm_thread.cancel()
            self.set_status("Stopping…")

    def _on_escape(self):
        if self._is_busy():
            self._on_stop()

    def _retry_last(self):
        if self._is_busy():
            return
        if not any(m["role"] == "user" for m in self.history):
            log.warning("Retry requested but no user message in history")
            self.set_status("Nothing to retry.")
            return
        log.info("Retrying last request")
        # Drop the failed request's bubbles (error notice and any unpersisted
        # partial answer), then ask again using the existing history.
        self._remove_bubble(self._last_error_bubble)
        self._last_error_bubble = None
        self._remove_bubble(self._last_partial_bubble)
        self._last_partial_bubble = None
        self.input_area.set_loading(True)
        self._start_request()

    @pyqtSlot()
    def _on_thread_finished(self):
        thread = self.sender()
        if thread is self.llm_thread:
            self.llm_thread = None
        if isinstance(thread, LLMThread):
            self._threads.discard(thread)
            log.debug("LLM thread finished and cleaned up")
            thread.deleteLater()

    # -- scratchpad ------------------------------------------------------

    def _ensure_scratchpad(self) -> ScratchpadWidget:
        if self.scratchpad is None:
            self.scratchpad = ScratchpadWidget(self)
            self.scratchpad.run_requested.connect(self._send_scratchpad_code)
        return self.scratchpad

    def _toggle_scratchpad(self):
        scratchpad = self._ensure_scratchpad()
        if scratchpad.isVisible():
            scratchpad.hide()
        else:
            scratchpad.show()
            scratchpad.raise_()
            scratchpad.activateWindow()

    def _open_scratchpad_with_code(self, code: str):
        scratchpad = self._ensure_scratchpad()
        scratchpad.editor.setPlainText(code)
        scratchpad.show()
        scratchpad.raise_()
        scratchpad.activateWindow()
        scratchpad.status_label.setText("Code loaded from the transcript.")

    def _send_scratchpad_code(self, code: str):
        if self.scratchpad is not None:
            self.scratchpad.hide()
        self._on_send(f"Please review this code I'm working on:\n\n```python\n{code}\n```")

    # -- session / export ------------------------------------------------

    def new_session(self):
        if self._is_busy():
            QMessageBox.warning(self, "Busy", "Stop the current answer first.")
            return

        reply = QMessageBox.question(
            self, "New Session",
            "Clear the transcript and saved history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        log.info("Starting new session")
        self.history.clear()
        clear_session()
        self._clear_messages()
        self.starters_widget.show()
        self.set_status("New session started")

    def export_transcript(self):
        if not self.history:
            QMessageBox.information(self, "Export", "Nothing to export yet.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Transcript", "python-tutor-session.md",
            "Markdown (*.md);;Text (*.txt);;All Files (*)",
        )
        if not path:
            return

        lines = [
            "# Python Tutor Session",
            "",
            f"- Level: {self.config.level}",
            f"- Model: {self.config.model}",
            "",
        ]
        for message in self.history:
            role = "You" if message["role"] == "user" else "Tutor"
            lines.append(f"## {role}\n\n{message['content']}\n")

        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            log.info("Transcript exported", path=path)
            self.set_status(f"Exported to {Path(path).name}")
        except OSError as exc:
            log.error("Export failed", error=str(exc))
            QMessageBox.critical(self, "Export Failed", str(exc))

    # -- settings --------------------------------------------------------

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.load_settings(self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply_settings(self.config)
            self.config.save()
            self.set_status("Settings saved")

    def _show_about(self):
        version = QApplication.applicationVersion() or "2.0"
        QMessageBox.about(
            self, "About Python Tutor",
            f"Python Tutor {version}\n\n"
            "Interactive Python learning with PyQt6\n"
            "OpenRouter API · Markdown rendering · Syntax highlighting",
        )

    # -- zoom ------------------------------------------------------------

    def _zoom_in(self):
        self._set_zoom(self._zoom + 1)

    def _zoom_out(self):
        self._set_zoom(self._zoom - 1)

    def _reset_zoom(self):
        self._set_zoom(0)

    def _set_zoom(self, steps: int):
        self._zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, steps))
        for bubble in self._bubbles:
            bubble.apply_zoom(self._zoom)
        self.set_status(f"Zoom {self._zoom:+d}" if self._zoom else "Zoom reset")

    # -- window state ----------------------------------------------------

    def _restore_state(self):
        if self.config.geometry:
            self.restoreGeometry(self.config.geometry)
        if self.config.window_state:
            self.restoreState(self.config.window_state)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def set_status(self, msg: str):
        self.statusBar().showMessage(msg, 6000)

    def closeEvent(self, event):
        running = [thread for thread in self._threads if thread.isRunning()]
        if running:
            if self._closing:
                # A second close request while we are already shutting down:
                # keep waiting for the worker rather than destroying a live
                # QThread when the app exits.
                event.ignore()
                return
            self._closing = True
            self._close_deadline = time.monotonic() + 4.0
            for thread in running:
                thread.cancel()
            log.info("Close requested, cancelling running threads", count=len(running))
            self.set_status("Stopping the current answer before closing…")
            event.ignore()
            QTimer.singleShot(100, self._close_when_idle)
            return

        log.info("Saving window state and closing")
        self._save_window_state()
        event.accept()

    def _close_when_idle(self):
        running = [thread for thread in self._threads if thread.isRunning()]
        if running:
            if time.monotonic() < self._close_deadline:
                QTimer.singleShot(100, self._close_when_idle)
                return
            # Last resort: don't leave a QThread running while the app exits.
            log.warning("Force terminating threads after deadline", count=len(running))
            for thread in running:
                thread.terminate()
                thread.wait(500)
        self._closing = False
        self.close()

    def _save_window_state(self):
        for bubble in self._bubbles:
            bubble.shutdown_runs()
        save_session(self.history)
        self.config.geometry = self.saveGeometry()
        self.config.window_state = self.saveState()
        self.config.save()
        log.debug("Window state saved")
        self.config.save()


if __name__ == "__main__":
    from src.main import main

    sys.exit(main())
