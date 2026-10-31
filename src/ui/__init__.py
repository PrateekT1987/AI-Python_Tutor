"""UI package for Python Tutor."""

from .main_window import MainWindow
from .widgets import (
    MessageBubble,
    ScratchpadWidget,
    InputArea,
    ChatInput,
    LevelSelector,
    PythonHighlighter,
    MarkdownHighlighter,
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
]
