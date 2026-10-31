"""Syntax highlighting for Python code using QSyntaxHighlighter."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

if TYPE_CHECKING:
    from PyQt6.QtGui import QTextDocument


# One Dark / Monokai inspired colors
SYNTAX_COLORS = {
    "keyword": "#C678DD",      # Purple
    "builtin": "#56B6C2",      # Cyan
    "string": "#98C379",       # Green
    "comment": "#5C6370",      # Gray
    "number": "#D19A66",       # Orange
    "function": "#61AFEF",     # Blue
    "class": "#E5C07B",        # Yellow
    "decorator": "#C678EA",    # Light purple
    "operator": "#56B6C2",     # Cyan
    "punctuation": "#ABB2BF",  # Foreground
}

# Python keywords
KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "match", "case", "type",
}

# Python builtins
BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
    "bytes", "callable", "chr", "classmethod", "compile", "complex", "delattr",
    "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter", "float",
    "format", "frozenset", "getattr", "globals", "hasattr", "hash", "help",
    "hex", "id", "input", "int", "isinstance", "issubclass", "iter", "len",
    "list", "locals", "map", "max", "memoryview", "min", "next", "object",
    "oct", "open", "ord", "pow", "print", "property", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
    "str", "sum", "super", "tuple", "type", "vars", "zip", "__import__",
}

# Common function names (stdlib)
FUNCTIONS = {
    "print", "len", "range", "enumerate", "zip", "map", "filter", "sorted",
    "min", "max", "sum", "abs", "round", "open", "input", "isinstance",
    "issubclass", "hasattr", "getattr", "setattr", "delattr", "type",
    "isinstance", "issubclass", "callable", "iter", "next", "reversed",
    "enumerate", "zip", "map", "filter", "all", "any", "sum", "max", "min",
    "open", "input", "print", "int", "float", "str", "bool", "list", "dict",
    "set", "tuple", "frozenset", "bytes", "bytearray", "memoryview",
    "object", "property", "classmethod", "staticmethod", "property",
    "super", "vars", "dir", "help", "compile", "eval", "exec", "globals",
    "locals", "id", "hash", "hex", "oct", "bin", "chr", "ord", "ascii",
    "repr", "format", "slice", "property", "classmethod", "staticmethod",
}

# Common class names
CLASSES = {
    "Exception", "Error", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "StopIteration", "GeneratorExit",
    "KeyboardInterrupt", "SystemExit", "BaseException", "OSError", "IOError",
    "FileNotFoundError", "PermissionError", "ConnectionError", "TimeoutError",
    "ValueError", "TypeError", "NameError", "SyntaxError", "IndentationError",
    "UnicodeError", "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeTranslateError",
    "list", "dict", "set", "tuple", "str", "int", "float", "bool", "complex",
    "bytes", "bytearray", "memoryview", "object", "type", "property",
    "classmethod", "staticmethod", "property", "super", "object",
}


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code."""
    
    def __init__(self, document: "QTextDocument"):
        super().__init__(document)
        self._setup_formats()
        self._build_patterns()
    
    def _setup_formats(self):
        """Create QTextCharFormat for each syntax element."""
        self.formats = {}
        
        for name, color in SYNTAX_COLORS.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if name in ("keyword", "class", "function", "decorator"):
                fmt.setFontWeight(QFont.Weight.Bold)
            self.formats[name] = fmt
        
        # Default text format
        self.formats["default"] = QTextCharFormat()
        self.formats["default"].setForeground(QColor("#ABB2BF"))
    
    def _build_patterns(self):
        """Build regex patterns for highlighting."""
        # Combined pattern with named groups
        keywords = "|".join(sorted(KEYWORDS, key=len, reverse=True))
        builtins = "|".join(sorted(BUILTINS, key=len, reverse=True))
        functions = "|".join(sorted(FUNCTIONS, key=len, reverse=True))
        classes = "|".join(sorted(CLASSES, key=len, reverse=True))
        
        self._pattern = re.compile(
            r"""
            (?P<comment>\#[^\n]*)
          | (?P<string>
                \"\"\"[\s\S]*?\"\"\"
              | '''[\s\S]*?'''
              | "(?:\\.|[^"\\])*"
              | '(?:\\.|[^'\\])*'
            )
          | (?P<number>
                \b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)\b
            )
          | (?P<keyword>\b(?:%s)\b)
          | (?P<builtin>\b(?:%s)\b)
          | (?P<function>\b(?:%s)\b)
          | (?P<class>\b(?:%s)\b)
          | (?P<decorator>@\w+)
            """
            % (keywords, builtins, functions, classes),
            re.MULTILINE,
        )
    
    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a text block."""
        for match in self._pattern.finditer(text):
            kind = match.lastgroup
            if not kind:
                continue
            
            fmt = self.formats.get(kind, self.formats["default"])
            start, end = match.span()
            self.setFormat(start, end - start, fmt)


class MarkdownHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for markdown text in QTextEdit."""
    
    def __init__(self, document):
        super().__init__(document)
        self._setup_formats()
        self._build_patterns()
    
    def _setup_formats(self):
        self.formats = {
            "header": QTextCharFormat(),
            "bold": QTextCharFormat(),
            "italic": QTextCharFormat(),
            "code": QTextCharFormat(),
            "link": QTextCharFormat(),
            "code_block": QTextCharFormat(),
        }
        
        # Header
        self.formats["header"].setForeground(QColor("#61AFEF"))
        self.formats["header"].setFontWeight(QFont.Weight.Bold)
        self.formats["header"].setFontPointSize(14)
        
        # Bold
        self.formats["bold"].setForeground(QColor("#E5C07B"))
        self.formats["bold"].setFontWeight(QFont.Weight.Bold)
        
        # Italic
        self.formats["italic"].setForeground(QColor("#98C379"))
        self.formats["italic"].setFontItalic(True)
        
        # Inline code
        self.formats["code"].setForeground(QColor("#E5C07B"))
        self.formats["code"].setFontFamily("JetBrains Mono, Consolas, monospace")
        self.formats["code"].setBackground(QColor("#282C34"))
        
        # Links
        self.formats["link"].setForeground(QColor("#61AFEF"))
        self.formats["link"].setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        
        # Code blocks
        self.formats["code_block"].setBackground(QColor("#282C34"))
        self.formats["code_block"].setForeground(QColor("#ABB2BF"))
        self.formats["code_block"].setFontFamily("JetBrains Mono, Consolas, monospace")
    
    def _build_patterns(self):
        self.patterns = [
            (re.compile(r"^(#{1,6})\s+(.+)$"), "header"),
            (re.compile(r"\*\*(.+?)\*\*"), "bold"),
            (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), "italic"),
            (re.compile(r"`([^`\n]+)`"), "code"),
        ]
    
    def highlightBlock(self, text: str):
        for pattern, fmt_name in self.patterns:
            fmt = self.formats[fmt_name]
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)