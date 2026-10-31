"""Message bubble with markdown rendering and code execution."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QProcess,
    QProcessEnvironment,
    QTemporaryDir,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QDesktopServices, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.logging_setup import get_logger
from src.core.parsers import (
    parse_blocks,
    parse_table,
    render_table_html,
    render_text_html,
    escape_html,
)

log = get_logger(__name__)

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

        try:
            lexer = get_lexer_by_name(lang or "text", stripall=True)
        except ClassNotFound:
            lexer = TextLexer()

        formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=True)
        highlighted = highlight(code, lexer, formatter)
        label = escape_html((lang or "text").upper())

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

        # VS Code style: gutter slightly darker than code area, subtle right border.
        gutter_bg = "#1E1E1E"
        gutter_border = "#3C3C3C"
        code_bg = "#282C34"

        # Measure the widest code line so we can pick table-layout:fixed (short)
        # or table-layout:auto (long) without clipping.
        fm = QFontMetrics(self.content_edit.font())
        longest_px = 0
        for line in code.expandtabs(4).splitlines():
            longest_px = max(longest_px, fm.horizontalAdvance(line))
        code_width = longest_px + 24  # pre padding

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

        log.info("Code run requested", index=index, chars=len(self._code_blocks[index]))

        workdir = QTemporaryDir()
        if not workdir.isValid():
            log.error("Failed to create temporary directory for code execution")
            self._set_output(index, "Could not create a temporary directory.")
            return

        script = Path(workdir.path()) / "main.py"
        try:
            script.write_text(self._code_blocks[index], encoding="utf-8")
        except OSError as exc:
            log.error("Failed to write script", error=str(exc))
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
        log.info("Code execution finished", index=index, exit_code=exit_code, output_chars=len(output))
        self._set_output(index, output)
        self.status_message.emit(
            "Code finished" if exit_code == 0 else f"Code exited with status {exit_code}"
        )

    def _on_run_error(self, index: int, error: QProcess.ProcessError):
        if error == QProcess.ProcessError.FailedToStart:
            process = self._processes.get(index)
            detail = process.errorString() if process is not None else "unknown error"
            log.error("Code process failed to start", index=index, error=detail)
            self._cleanup_run(index)
            self._set_output(index, f"Could not start Python: {detail}")
        else:
            log.warning("Code process error", index=index, error=error.name)
        # Crashed / Timedout / WriteError are reported through finished().

    def _on_run_timeout(self, index: int):
        process = self._processes.get(index)
        if process is None:
            return
        log.warning("Code execution timed out, killing process", index=index)
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
        if self._processes:
            log.info("Shutting down running code processes", count=len(self._processes))
        for process in list(self._processes.values()):
            process.kill()
            process.waitForFinished(500)

    # -- sizing ----------------------------------------------------------

    def fit_width(self, available: int):
        """Fit the bubble into the readable column.

        Assistant answers fill the column so every reply shares the same
        comfortable right edge; user messages hug their content.
        """
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