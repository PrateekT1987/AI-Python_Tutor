"""Custom widgets for the chat interface."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QProcess,
    QProcessEnvironment,
    QRect,
    QSize,
    QTemporaryDir,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Variables that must never leak into code the tutor asked us to run.
_SECRET_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)


class MessageBubble(QFrame):
    """A chat message bubble with markdown rendering.

    Code blocks are rendered with Pygments, line numbers, and ``Run`` /
    ``Ask`` / ``Copy`` actions through link anchors handled by
    :meth:`_on_anchor`. ``Run`` executes the block in an isolated Python
    subprocess and appends its output beneath the block.
    """

    ask_requested = pyqtSignal(str)
    retry_requested = pyqtSignal()
    status_message = pyqtSignal(str)
    output_updated = pyqtSignal()

    MAX_WIDTH = 900
    MIN_WIDTH = 260
    RUN_TIMEOUT_MS = 10_000
    MAX_OUTPUT_CHARS = 6_000

    def __init__(
        self,
        role: str,
        content: str,
        parent: QWidget | None = None,
        retryable: bool = False,
        streaming: bool = False,
    ):
        super().__init__(parent)
        self.role = role  # "user" or "assistant"
        self.content = content
        self._code_blocks: list[str] = []
        self._code_outputs: dict[int, str] = {}
        self._running_blocks: set[int] = set()
        self._processes: dict[int, QProcess] = {}
        self._run_timers: dict[int, QTimer] = {}
        self._run_dirs: dict[int, QTemporaryDir] = {}
        self._available_width = self.MAX_WIDTH
        self._adjusting = False
        self._applied_zoom = 0
        self._streaming = streaming
        self._adjust_timer = QTimer(self)
        self._adjust_timer.setSingleShot(True)
        self._adjust_timer.setInterval(0)
        self._adjust_timer.timeout.connect(self._adjust_height)
        self._setup_ui(retryable)
        if content:
            self.set_content(content)
        elif streaming:
            self.set_streaming_text("")

    def _setup_ui(self, retryable: bool):
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumWidth(self.MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)

        # Header: role label + per-message actions
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.role_label = QLabel("You" if self.role == "user" else "Tutor")
        self.role_label.setFont(QFont("JetBrains Mono", 10))
        self.role_label.setStyleSheet(
            "color: #E5C07B; font-weight: 600;" if self.role == "user"
            else "color: #61AFEF; font-weight: 600;"
        )
        header.addWidget(self.role_label)
        header.addStretch(1)

        self.retry_btn = QToolButton()
        self.retry_btn.setText("Retry")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setToolTip("Send the last question again")
        self.retry_btn.setAccessibleName("Retry request")
        self.retry_btn.setStyleSheet(self._action_style())
        self.retry_btn.clicked.connect(self.retry_requested.emit)
        self.retry_btn.setVisible(retryable)
        header.addWidget(self.retry_btn)

        self.copy_btn = QToolButton()
        self.copy_btn.setText("Copy")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Copy this message as Markdown")
        self.copy_btn.setAccessibleName("Copy message")
        self.copy_btn.setStyleSheet(self._action_style())
        self.copy_btn.clicked.connect(self._copy_message)
        self.copy_btn.setVisible(False)
        header.addWidget(self.copy_btn)

        layout.addLayout(header)

        # Content area with HTML rendering
        self.content_edit = QTextBrowser()
        self.content_edit.setReadOnly(True)
        self.content_edit.setFrameStyle(0)
        self.content_edit.setOpenLinks(False)
        self.content_edit.setOpenExternalLinks(False)
        self.content_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.content_edit.setMinimumWidth(0)
        self.content_edit.setMinimumHeight(26)
        self.content_edit.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )
        self.content_edit.document().setDocumentMargin(0)
        body_font = self.content_edit.font()
        body_font.setPointSize(11)
        self.content_edit.setFont(body_font)
        self.content_edit.anchorClicked.connect(self._on_anchor)
        layout.addWidget(self.content_edit)

        if self.role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #333333;
                    border-radius: 12px;
                    border-bottom-right-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #252526;
                    border-radius: 12px;
                    border-bottom-left-radius: 4px;
                }
            """)

    @staticmethod
    def _action_style() -> str:
        return """
            QToolButton {
                background: transparent;
                color: #8B93A1;
                border: none;
                padding: 2px 6px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 10px;
            }
            QToolButton:hover { color: #ABB2BF; background: #3A3F4B; border-radius: 4px; }
        """

    # -- content ---------------------------------------------------------

    def set_content(self, content: str, keep_outputs: bool = False):
        """Render markdown content (used once streaming completes).

        ``keep_outputs`` re-renders the same content in place after a code
        block has run, preserving its captured output.
        """
        self.content = content
        self._streaming = False
        self._code_blocks = []
        if not keep_outputs:
            self._code_outputs.clear()
        from src.core.parsers import parse_blocks, parse_table, render_table_html, render_text_html

        parts: list[str] = []
        for block in parse_blocks(content):
            if block.kind == "code":
                index = len(self._code_blocks)
                self._code_blocks.append(block.value)
                parts.append(self._render_code_block(block.value, block.lang, index))
            elif block.kind == "table":
                rows, _ = parse_table(block.value)
                parts.append(render_table_html(rows))
            else:
                parts.append(render_text_html(block.value))

        self.content_edit.setHtml("".join(parts))
        self.copy_btn.setVisible(bool(content.strip()))
        self.fit_width(self._available_width)
        self._schedule_adjust()

    def set_streaming_text(self, text: str):
        """Render in-progress text efficiently (plain text + cursor)."""
        from src.core.parsers import escape_html

        self._streaming = True
        self.content = text
        self.copy_btn.setVisible(False)
        if self.width() != min(self._available_width, self.MAX_WIDTH):
            self.setFixedWidth(min(self._available_width, self.MAX_WIDTH))
        body = escape_html(text).replace("\n", "<br>")
        cursor = '<span style="color:#61AFEF;">▌</span>'
        if not body:
            cursor = '<span style="color:#7C8896;">Thinking…</span>' + cursor
        self.content_edit.setHtml(
            f'<div style="font-size:13px; line-height:1.45; color:#E6E6E6;">{body}{cursor}</div>'
        )
        self._schedule_adjust()

    def _render_code_block(self, code: str, lang: str, index: int) -> str:
        """Render a code block with line numbers, highlighting and actions."""
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name
        from pygments.lexers.special import TextLexer
        from pygments.util import ClassNotFound
        from src.core.parsers import escape_html

        try:
            lexer = get_lexer_by_name(lang or "text", stripall=True)
        except ClassNotFound:
            lexer = TextLexer()

        formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=True)
        highlighted = highlight(code, lexer, formatter)
        label = (lang or "text").upper()
        label = escape_html(label)

        line_count = max(1, len(code.splitlines()))
        numbers = "\n".join(str(number) for number in range(1, line_count + 1))
        gutter_width = 22 + 8 * len(str(line_count))
        mono = "'JetBrains Mono','Fira Code','Consolas',monospace"

        if index in self._running_blocks:
            run_action = '<span style="color:#E5C07B; text-decoration:none;">Running…</span>'
        else:
            run_action = (
                f'<a href="run:{index}" style="color:#98C379; text-decoration:none;">'
                "▶ Run</a>"
            )

        header = (
            '<table cellspacing="0" cellpadding="0" '
            'style="margin:10px 0 0 0; background-color:#2A2E38; table-layout:auto;">'
            "<tr>"
            f'<td style="padding:5px 10px; color:#ADB5C2; font-family:{mono}; '
            f'font-size:11px;">{label}</td>'
            '<td align="right" style="padding:5px 10px; font-size:12px;">'
            f"{run_action}"
            "&nbsp;&nbsp;&nbsp;"
            f'<a href="ask:{index}" style="color:#61AFEF; text-decoration:none;">Ask</a>'
            "&nbsp;&nbsp;&nbsp;"
            f'<a href="copy:{index}" style="color:#61AFEF; text-decoration:none;">Copy</a>'
            "</td></tr></table>"
        )

        has_output = index in self._running_blocks or index in self._code_outputs
        body_margin = "0" if has_output else "0 0 10px 0"

        # Measure the widest code line so we can pick table-layout:fixed (short)
        # or table-layout:auto (long) without clipping.
        fm = QFontMetrics(self.content_edit.font())
        longest_px = 0
        for line in code.expandtabs(4).splitlines():
            longest_px = max(longest_px, fm.horizontalAdvance(line))
        code_width = longest_px + 24  # pre padding

        # VS Code style: gutter slightly darker than code area, subtle right border.
        gutter_bg = "#1E1E1E"
        gutter_border = "#3C3C3C"
        code_bg = "#282C34"

        if code_width <= self._available_width - 60:
            # Short enough for fixed table layout (cleaner look).
            body = (
                '<table width="100%" cellspacing="0" cellpadding="0" '
                f'style="margin:{body_margin}; background-color:{code_bg}; table-layout:fixed;">'
                "<tr>"
                f'<td width="{gutter_width}" valign="top" '
                f'style="padding:10px 8px 10px 12px; background-color:{gutter_bg}; '
                f'border-right:1px solid {gutter_border};">'
                f'<pre style="margin:0; color:#7C8896; font-family:{mono}; '
                f'font-size:12px; text-align:right;">{numbers}</pre>'
                "</td>"
                '<td valign="top" style="padding:10px 12px;">'
                f'<pre style="margin:0; color:#E6E6E6; font-family:{mono}; '
                f'font-size:12px;">{highlighted}</pre>'
                "</td></tr></table>"
            )
        else:
            # Long line: let the table expand and the browser show an h-scrollbar.
            body = (
                '<table cellspacing="0" cellpadding="0" '
                f'style="margin:{body_margin}; background-color:{code_bg}; table-layout:auto;">'
                "<tr>"
                f'<td valign="top" '
                f'style="padding:10px 8px 10px 12px; background-color:{gutter_bg}; '
                f'border-right:1px solid {gutter_border};">'
                f'<pre style="margin:0; color:#7C8896; font-family:{mono}; '
                f'font-size:12px; text-align:right;">{numbers}</pre>'
                "</td>"
                '<td valign="top" style="padding:10px 12px;">'
                f'<pre style="margin:0; color:#E6E6E6; font-family:{mono}; '
                f'font-size:12px;">{highlighted}</pre>'
                "</td></tr></table>"
            )

        return header + body + self._render_output(index)

    def _render_output(self, index: int) -> str:
        """Render the captured output (or running state) below a code block."""
        running = index in self._running_blocks
        if not running and index not in self._code_outputs:
            return ""
        from src.core.parsers import escape_html

        mono = "'JetBrains Mono','Fira Code','Consolas',monospace"
        if running:
            content = '<span style="color:#E5C07B;">Running in a Python subprocess…</span>'
        else:
            text = self._code_outputs[index]
            color = "#98C379" if text.startswith("(no output)") else "#F0F0F0"
            content = (
                f'<pre style="margin:4px 0 0 0; color:{color}; font-family:{mono}; '
                f'font-size:12px;">{escape_html(text)}</pre>'
            )

        # A single-cell table paints a solid panel; a styled <div> would only
        # tint the individual text lines.
        return (
            '<table cellspacing="0" cellpadding="0" '
            'style="margin:0 0 10px 0; background-color:#15181D; table-layout:auto;">'
            '<tr><td style="padding:8px 12px; border-left:3px solid #61AFEF;">'
            f'<span style="color:#9AA6B8; font-family:{mono}; font-size:10px; '
            f'letter-spacing:1px;">OUTPUT</span>'
            f"{content}</td></tr></table>"
        )

    # -- actions ---------------------------------------------------------

    def _copy_message(self):
        QApplication.clipboard().setText(self.content)
        self.status_message.emit("Message copied to clipboard")

    def _copy_code(self, index: int):
        if 0 <= index < len(self._code_blocks):
            QApplication.clipboard().setText(self._code_blocks[index])
            self.status_message.emit("Code copied to clipboard")

    def _on_anchor(self, url: QUrl):
        href = url.toString()
        if href.startswith("copy:"):
            try:
                self._copy_code(int(href.split(":", 1)[1]))
            except ValueError:
                pass
        elif href.startswith("ask:"):
            try:
                index = int(href.split(":", 1)[1])
            except ValueError:
                return
            if 0 <= index < len(self._code_blocks):
                self.ask_requested.emit(self._code_blocks[index])
        elif href.startswith("run:"):
            try:
                index = int(href.split(":", 1)[1])
            except ValueError:
                return
            self._run_code(index)
        elif href.startswith("retry:"):
            self.retry_requested.emit()
        elif url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)

    # -- code execution ---------------------------------------------------

    def _run_code(self, index: int):
        """Run one code block in an isolated Python subprocess.

        The child gets a temporary working directory and a copy of the
        environment with credentials removed, so tutor code cannot read the
        app's API keys. Execution is user-initiated by clicking ``Run``.
        """
        if not (0 <= index < len(self._code_blocks)) or index in self._running_blocks:
            return

        workdir = QTemporaryDir()
        if not workdir.isValid():
            self._set_output(index, "Could not create a temporary directory.")
            return

        script = Path(workdir.path()) / "main.py"
        try:
            script.write_text(self._code_blocks[index], encoding="utf-8")
        except OSError as exc:
            workdir.remove()
            self._set_output(index, f"Could not write the script: {exc}")
            return

        env = QProcessEnvironment.systemEnvironment()
        for name in _SECRET_ENV_VARS:
            env.remove(name)
        env.insert("PYTHONUNBUFFERED", "1")

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(workdir.path())
        process.setProcessEnvironment(env)
        process.finished.connect(
            lambda exit_code, _status, idx=index: self._on_run_finished(idx, exit_code)
        )
        process.errorOccurred.connect(
            lambda error, idx=index: self._on_run_error(idx, error)
        )

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda idx=index: self._on_run_timeout(idx))

        self._processes[index] = process
        self._run_timers[index] = timer
        self._run_dirs[index] = workdir
        self._running_blocks.add(index)
        self._code_outputs.pop(index, None)
        self._set_output(index, "")
        self.status_message.emit("Running code…")
        process.start(sys.executable, ["-u", str(script)])
        timer.start(self.RUN_TIMEOUT_MS)

    def _cleanup_run(self, index: int):
        self._running_blocks.discard(index)
        timer = self._run_timers.pop(index, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        self._processes.pop(index, None)
        workdir = self._run_dirs.pop(index, None)
        if workdir is not None:
            workdir.remove()

    def _on_run_finished(self, index: int, exit_code: int):
        process = self._processes.get(index)
        if process is None:
            return
        output = bytes(process.readAllStandardOutput()).decode("utf-8", "replace").strip()
        self._cleanup_run(index)
        if not output:
            output = "(no output)"
        if exit_code != 0:
            output += f"\n\n[exit code {exit_code}]"
        self._set_output(index, output)
        self.status_message.emit(
            "Code finished" if exit_code == 0 else f"Code exited with status {exit_code}"
        )

    def _on_run_error(self, index: int, error: QProcess.ProcessError):
        if error == QProcess.ProcessError.FailedToStart:
            process = self._processes.get(index)
            detail = process.errorString() if process is not None else "unknown error"
            self._cleanup_run(index)
            self._set_output(index, f"Could not start Python: {detail}")
        # Crashed / Timedout / WriteError are reported through finished().

    def _on_run_timeout(self, index: int):
        process = self._processes.get(index)
        if process is None:
            return
        process.kill()
        self._cleanup_run(index)
        seconds = max(1, round(self.RUN_TIMEOUT_MS / 1000))
        self._set_output(
            index,
            f"Stopped after {seconds}s (possible infinite loop).",
        )
        self.status_message.emit("Code timed out")

    def _set_output(self, index: int, output: str):
        """Store an output string and re-render the code block in place."""
        if len(output) > self.MAX_OUTPUT_CHARS:
            output = output[: self.MAX_OUTPUT_CHARS] + "\n… output truncated"
        if output:
            self._code_outputs[index] = output
        self.set_content(self.content, keep_outputs=True)
        self.output_updated.emit()

    def shutdown_runs(self):
        """Kill any running child processes (used when the window closes)."""
        for process in list(self._processes.values()):
            process.kill()
            process.waitForFinished(500)

    # -- sizing ----------------------------------------------------------

    def fit_width(self, available: int):
        """Fit the bubble into the readable column.

        Assistant answers fill the column so every reply shares the same
        comfortable right edge; user messages hug their content.
        """
        from PyQt6.QtGui import QFontMetrics

        self._available_width = max(self.MIN_WIDTH, int(available))
        target = min(self.MAX_WIDTH, self._available_width)

        if self.role == "user":
            metrics = QFontMetrics(self.content_edit.font())
            longest = 0
            for line in self.content.splitlines() or [""]:
                longest = max(longest, metrics.horizontalAdvance(line.expandtabs(4)))
            # + bubble padding and header affordances
            target = max(self.MIN_WIDTH, min(target, longest + 64))

        if self.width() != target:
            self.setFixedWidth(target)
        self._schedule_adjust()

    def _schedule_adjust(self):
        self._adjust_timer.start()

    def _adjust_height(self):
        if self._adjusting:
            return
        width = self.content_edit.viewport().width()
        if width <= 0:
            return
        doc = self.content_edit.document()
        doc.setTextWidth(width)
        size = doc.documentLayout().documentSize()
        height = math.ceil(size.height()) + 2
        if size.width() > width:
            height += 12  # room for the horizontal scrollbar
        height = max(height, 26)
        if abs(self.content_edit.height() - height) > 1:
            self._adjusting = True
            self.content_edit.setFixedHeight(height)
            self._adjusting = False

    def apply_zoom(self, steps: int):
        """Apply a cumulative zoom level (in Qt font-size steps)."""
        delta = steps - self._applied_zoom
        if delta:
            self.content_edit.zoomIn(delta)
            self._applied_zoom = steps
            self._schedule_adjust()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()


class LineNumberArea(QWidget):
    """Gutter that paints the line numbers for a :class:`CodeEditor`."""

    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Code editor with a line-number gutter and no soft wrapping."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._line_number_area = LineNumberArea(self)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width(0)

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _count: int):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        area = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(area.left(), area.top(), self.line_number_area_width(), area.height())
        )

    def paint_line_numbers(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#1A1D22"))
        painter.setPen(QColor("#8B93A1"))

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        offset = self.contentOffset()
        top = round(self.blockBoundingGeometry(block).translated(offset).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        text_height = self.fontMetrics().height()
        text_width = self._line_number_area.width() - 8
        flags = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, top, text_width, text_height, flags, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1


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

    def _scratch_path(self):
        from src.core.settings import config_dir
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
    """Input area with integrated Run/Stop buttons."""

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

        # Run button
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
        from PyQt6.QtGui import QFontMetrics

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

    def set_side_margins(self, side: int):
        """Align the composer with the centred transcript column."""
        layout = self.layout()
        if layout is not None:
            layout.setContentsMargins(side, 12, side, 12)

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
