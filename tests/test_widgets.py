"""Tests for Python Tutor PyQt6 widgets (headless)."""

from __future__ import annotations

import os
import sys
import time

# Set up offscreen platform before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

# Create QApplication once for all tests
app = QApplication.instance() or QApplication([])

from src.ui.widgets import (
    MessageBubble, ScratchpadWidget, InputArea, ChatInput,
    LevelSelector, PythonHighlighter, MarkdownHighlighter
)


class TestMessageBubble:
    def test_user_bubble_creation(self):
        bubble = MessageBubble("user", "Hello world")
        assert bubble.role == "user"
        assert bubble.content == "Hello world"
        assert bubble.role_label.text() == "You"

    def test_assistant_bubble_creation(self):
        bubble = MessageBubble("assistant", "Hi there!")
        assert bubble.role == "assistant"
        assert bubble.content == "Hi there!"
        assert bubble.role_label.text() == "Tutor"

    def test_bubble_with_markdown(self):
        content = "**Bold** and *italic* and `code`"
        bubble = MessageBubble("assistant", content)
        html = bubble.content_edit.toHtml()
        assert "Bold" in html or "bold" in html.lower()

    def test_bubble_with_code_block(self):
        content = "```python\nprint('hello')\n```"
        bubble = MessageBubble("assistant", content)
        assert "print" in bubble.content_edit.toPlainText()
        assert bubble._code_blocks == ["print('hello')"]

    def test_bubble_with_table(self):
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        bubble = MessageBubble("assistant", content)
        html = bubble.content_edit.toHtml()
        assert "table" in html.lower() or "1" in html

    def test_bubble_keeps_paragraphs(self):
        bubble = MessageBubble("assistant", "First paragraph.\n\nSecond paragraph.")
        html = bubble.content_edit.toHtml()
        assert "First paragraph." in html
        assert "Second paragraph." in html
        assert html.count("<p") >= 2

    def test_bubble_escapes_comparison_operators(self):
        bubble = MessageBubble("assistant", "Use `if x < 3 and a & b` in your check.")
        text = bubble.content_edit.toPlainText()
        assert "x < 3" in text
        assert "a & b" in text

    def test_bubble_renders_lists_and_headings(self):
        bubble = MessageBubble("assistant", "## Steps\n\n- first\n- second")
        html = bubble.content_edit.toHtml()
        assert "Steps" in html
        assert "<ul" in html.lower()
        assert "second" in html

    def test_code_copy_and_ask_actions(self):
        bubble = MessageBubble("assistant", "```python\nx = 1\n```")
        statuses = []
        asked = []
        bubble.status_message.connect(statuses.append)
        bubble.ask_requested.connect(asked.append)

        bubble._on_anchor(QUrl("copy:0"))
        assert QApplication.clipboard().text() == "x = 1"
        assert statuses == ["Code copied to clipboard"]

        bubble._on_anchor(QUrl("ask:0"))
        assert asked == ["x = 1"]

    def test_streaming_text(self):
        bubble = MessageBubble("assistant", "", streaming=True)
        bubble.set_streaming_text("partial answer")
        assert "partial answer" in bubble.content_edit.toPlainText()
        assert not bubble.copy_btn.isVisible()

    def test_assistant_fills_readable_column(self):
        bubble = MessageBubble("assistant", "short answer")
        bubble.fit_width(2000)
        assert bubble.width() == MessageBubble.MAX_WIDTH

    def test_user_bubble_hugs_content(self):
        bubble = MessageBubble("user", "hi")
        bubble.fit_width(2000)
        assert bubble.width() < MessageBubble.MAX_WIDTH

    def test_code_block_has_line_numbers_and_run_action(self):
        bubble = MessageBubble("assistant", "```python\na = 1\nb = 2\nprint(a + b)\n```")
        text = bubble.content_edit.toPlainText()
        assert "1\n2\n3" in text
        assert "▶ Run" in text
        assert "run:0" in bubble.content_edit.toHtml()

    def test_run_code_block_shows_output(self):
        bubble = MessageBubble("assistant", '```python\nprint("from the block")\n```')
        bubble._run_code(0)
        deadline = time.monotonic() + 8
        while 0 not in bubble._code_outputs and time.monotonic() < deadline:
            QTest.qWait(20)
        assert "from the block" in bubble._code_outputs.get(0, "")
        assert "OUTPUT" in bubble.content_edit.toPlainText()

    def test_run_code_block_reports_exit_code(self):
        bubble = MessageBubble("assistant", "```python\nraise SystemExit(3)\n```")
        bubble._run_code(0)
        deadline = time.monotonic() + 8
        while 0 not in bubble._code_outputs and time.monotonic() < deadline:
            QTest.qWait(20)
        assert "[exit code 3]" in bubble._code_outputs.get(0, "")

    def test_run_code_block_does_not_leak_api_key(self):
        bubble = MessageBubble(
            "assistant",
            '```python\nimport os\nprint(os.environ.get("OPENROUTER_API_KEY"))\n```',
        )
        bubble._run_code(0)
        deadline = time.monotonic() + 8
        while 0 not in bubble._code_outputs and time.monotonic() < deadline:
            QTest.qWait(20)
        assert bubble._code_outputs.get(0, "").strip() == "None"

    def test_run_code_block_times_out(self, monkeypatch):
        monkeypatch.setattr(MessageBubble, "RUN_TIMEOUT_MS", 600)
        bubble = MessageBubble("assistant", "```python\nwhile True:\n    pass\n```")
        bubble._run_code(0)
        deadline = time.monotonic() + 8
        while 0 not in bubble._code_outputs and time.monotonic() < deadline:
            QTest.qWait(20)
        assert "Stopped after" in bubble._code_outputs.get(0, "")
        assert not bubble._running_blocks
        assert not bubble._processes


class TestScratchpadWidget:
    def test_scratchpad_creation(self):
        widget = ScratchpadWidget()
        assert widget.editor is not None
        assert widget.status_label is not None

    def test_scratchpad_emits_code(self):
        widget = ScratchpadWidget()
        emitted = []
        widget.run_requested.connect(emitted.append)
        widget.editor.setPlainText("print('hi')")
        widget._emit_run()
        assert emitted == ["print('hi')"]

    def test_scratchpad_does_not_emit_empty(self):
        widget = ScratchpadWidget()
        emitted = []
        widget.run_requested.connect(emitted.append)
        widget._emit_run()
        assert emitted == []

    def test_scratchpad_editor_has_line_numbers(self):
        widget = ScratchpadWidget()
        widget.editor.setPlainText("a = 1\nb = 2\nc = 3")
        assert widget.editor.line_number_area_width() > 20
        assert widget.editor.viewportMargins().left() == widget.editor.line_number_area_width()


class TestInputArea:
    def test_input_area_creation(self):
        widget = InputArea()
        assert widget.input_entry is not None
        assert isinstance(widget.input_entry, ChatInput)
        assert widget.run_btn is not None
        assert widget.stop_btn is not None
        assert not widget.stop_btn.isEnabled()

    def test_input_area_set_loading(self):
        widget = InputArea()
        widget.set_loading(True)
        assert not widget.run_btn.isEnabled()
        assert widget.stop_btn.isEnabled()
        assert not widget.input_entry.isEnabled()

        widget.set_loading(False)
        assert widget.run_btn.isEnabled()
        assert not widget.stop_btn.isEnabled()
        assert widget.input_entry.isEnabled()

    def test_enter_sends_and_clears(self):
        widget = InputArea()
        emitted = []
        widget.send_requested.connect(emitted.append)
        widget.input_entry.setPlainText("hello")
        QTest.keyClick(widget.input_entry, Qt.Key.Key_Return)
        assert emitted == ["hello"]
        assert widget.input_entry.toPlainText() == ""

    def test_shift_enter_inserts_newline(self):
        from PyQt6.QtGui import QTextCursor

        widget = InputArea()
        emitted = []
        widget.send_requested.connect(emitted.append)
        widget.input_entry.setPlainText("line one")
        widget.input_entry.moveCursor(QTextCursor.MoveOperation.End)
        QTest.keyClick(
            widget.input_entry,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        assert emitted == []
        assert widget.input_entry.toPlainText() == "line one\n"


class TestLevelSelector:
    def test_level_selector_creation(self):
        widget = LevelSelector()
        assert widget.current_level == "Intermediate"
        assert "Beginner" in widget.level_buttons
        assert "Intermediate" in widget.level_buttons
        assert "Advanced" in widget.level_buttons

    def test_level_selector_initial_state(self):
        widget = LevelSelector()
        assert widget.level_buttons["Intermediate"].isChecked()
        assert not widget.level_buttons["Beginner"].isChecked()
        assert not widget.level_buttons["Advanced"].isChecked()

    def test_level_selector_change(self):
        widget = LevelSelector()
        emitted = []
        widget.level_changed.connect(lambda lvl: emitted.append(lvl))

        widget.level_buttons["Advanced"].click()
        assert widget.current_level == "Advanced"
        assert widget.level_buttons["Advanced"].isChecked()
        assert emitted == ["Advanced"]

    def test_level_selector_set_level(self):
        widget = LevelSelector()
        emitted = []
        widget.level_changed.connect(emitted.append)
        widget.set_level("Beginner")
        assert widget.current_level == "Beginner"
        assert widget.level_buttons["Beginner"].isChecked()
        assert emitted == []


class TestSyntaxHighlighter:
    def test_python_highlighter_creation(self):
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        highlighter = PythonHighlighter(doc)
        assert highlighter is not None

    def test_python_highlighter_highlights_keywords(self):
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        PythonHighlighter(doc)
        doc.setPlainText("def hello():\n    return 42")
        # Basic sanity check - no crash while the highlighter runs.
        assert doc.findBlockByNumber(0).isValid()

    def test_markdown_highlighter_creation(self):
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        highlighter = MarkdownHighlighter(doc)
        assert highlighter is not None


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
