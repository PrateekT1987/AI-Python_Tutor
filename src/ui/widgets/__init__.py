"""UI widgets package."""

from .code_editor import CodeEditor, LineNumberArea
from .input_area import InputArea, ChatInput
from .level_selector import LevelSelector
from .message_bubble import MessageBubble
from .scratchpad import ScratchpadWidget
from .syntax_highlighter import PythonHighlighter, MarkdownHighlighter

__all__ = [
    "CodeEditor",
    "LineNumberArea",
    "InputArea",
    "ChatInput",
    "LevelSelector",
    "MessageBubble",
    "ScratchpadWidget",
    "PythonHighlighter",
    "MarkdownHighlighter",
]