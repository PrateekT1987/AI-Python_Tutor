"""UI package for Python Tutor."""

from __future__ import annotations

from .main_window import MainWindow
from .widgets import (
    MessageBubble,
    ScratchpadWidget,
    InputArea,
    ChatInput,
    LevelSelector,
    PythonHighlighter,
    MarkdownHighlighter,
    CodeEditor,
    LineNumberArea,
)

__all__ = [
    "MainWindow",
    "MessageBubble",
    "ScratchpadWidget",
    "InputArea",
    "ChatInput",
    "LevelSelector",
    "PythonHighlighter",
    "MarkdownHighlighter",
    "CodeEditor",
    "LineNumberArea",
]