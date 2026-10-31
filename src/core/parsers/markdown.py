"""Markdown parsing utilities for Python Tutor.

Handles parsing of markdown into structured blocks (text, code, tables),
inline markdown elements (bold, italic, inline code, links), and rendering
prose blocks to the HTML subset supported by Qt rich text.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|\s*[-:]+\s*\|")

# Inline markdown patterns
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")

# Combined inline tokenizer used for HTML rendering.
_INLINE_TOKEN = re.compile(
    r"`(?P<code>[^`\n]+)`"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|__(?P<bold2>.+?)__"
    r"|(?<!\*)\*(?P<italic>[^*\n]+)\*(?!\*)"
    r"|\[(?P<linktext>[^\]\n]*)\]\((?P<linkurl>[^)\s]+)\)"
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UNORDERED = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

_SAFE_LINK = re.compile(r"^(?:https?:|mailto:)", re.IGNORECASE)

# Text styles used by rendered prose. Kept inline because Qt rich text does
# not reliably apply document-level stylesheets inside QTextBrowser.
_BODY_STYLE = "margin:0 0 10px 0;"
_CODE_STYLE = (
    "background-color:#2C313A; color:#E5C07B; font-family:'JetBrains Mono',"
    "'Fira Code','Consolas',monospace; font-size:12px;"
)


@dataclass(frozen=True)
class Block:
    """A parsed markdown block."""
    kind: str          # "text", "code", or "table"
    value: str
    lang: str = ""


@dataclass(frozen=True)
class InlineSpan:
    """Represents an inline markdown element."""
    type: str  # "bold", "italic", "code", "text"
    text: str


def _lang_from_info(info: str) -> str:
    info = info.strip()
    if not info:
        return ""
    return info.split()[0].strip(".,:").lower()


def _is_close(line: str, marker: str) -> bool:
    stripped = line.strip()
    return (
        len(stripped) >= len(marker)
        and set(stripped) == {marker[0]}
    )


def _is_table_row(line: str) -> bool:
    return bool(_TABLE_ROW.match(line.strip()))


def _is_table_sep(line: str) -> bool:
    return bool(_TABLE_SEP.match(line.strip()))


def parse_blocks(text: str) -> list[Block]:
    """Split `text` into text/code/table blocks, preserving their order."""
    blocks: list[Block] = []
    text_buffer: list[str] = []
    code_buffer: list[str] = []
    table_buffer: list[str] = []
    marker = ""
    lang = ""
    in_table = False

    def flush_text() -> None:
        if text_buffer:
            value = "".join(text_buffer)
            if value.strip():
                blocks.append(Block("text", value))
            text_buffer.clear()

    def flush_code() -> None:
        blocks.append(Block("code", "".join(code_buffer).rstrip("\n"), lang))
        code_buffer.clear()

    def flush_table() -> None:
        if table_buffer:
            blocks.append(Block("table", "".join(table_buffer).rstrip("\n"), ""))
            table_buffer.clear()

    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")

        # Check for table separator
        if _is_table_sep(line):
            if not in_table:
                flush_text()
                in_table = True
            table_buffer.append(line)
            continue

        # Check for table row
        if _is_table_row(line):
            if not in_table:
                flush_text()
                in_table = True
            table_buffer.append(line)
            continue

        # Not a table line
        if in_table:
            flush_table()
            in_table = False

        if not marker:
            match = re.match(r"^(`{3,}|~{3,})(.*)$", bare)
            if match:
                flush_text()
                marker = match.group(1)
                lang = _lang_from_info(match.group(2))
            else:
                text_buffer.append(line)
        elif _is_close(bare, marker):
            flush_code()
            marker = ""
            lang = ""
        else:
            code_buffer.append(line)

    if marker:
        flush_code()
    if in_table:
        flush_table()
    flush_text()
    return blocks


def parse_inline(text: str) -> list[InlineSpan]:
    """Parse inline markdown (bold, italic, code) into spans."""
    spans: list[InlineSpan] = []
    last_end = 0

    for match in re.finditer(r"\*\*(.+?)\*\*|(?<!\*)\*([^*]+)\*(?!\*)|`([^`\n]+)`", text):
        start = match.start()
        if start > last_end:
            spans.append(InlineSpan("text", text[last_end:start]))

        if match.group(1) is not None:  # bold
            spans.append(InlineSpan("bold", match.group(1)))
        elif match.group(2) is not None:  # italic
            spans.append(InlineSpan("italic", match.group(2)))
        elif match.group(3) is not None:  # inline code
            spans.append(InlineSpan("code", match.group(3)))

        last_end = match.end()

    if last_end < len(text):
        spans.append(InlineSpan("text", text[last_end:]))

    return spans


def parse_table(text: str) -> tuple[list[list[str]], list[int]]:
    """Parse a markdown table into rows and column widths.

    Returns (rows, col_widths) where rows is list of cell lists.
    """
    lines = text.strip().split("\n")
    rows = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _is_table_sep(line):
            continue
        match = _TABLE_ROW.match(line)
        if match:
            cells = [cell.strip() for cell in match.group(1).split("|")]
            rows.append(cells)

    if not rows:
        return [], []

    # Calculate column widths
    num_cols = len(rows[0])
    col_widths = [0] * num_cols
    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))

    return rows, col_widths


def format_table(rows: list[list[str]], col_widths: list[int]) -> str:
    """Format a table as aligned text with borders."""
    if not rows:
        return ""

    lines = []
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            width = col_widths[j]
            cells.append(cell.ljust(width))
        lines.append(" │ ".join(cells))

        # Add separator after header
        if i == 0:
            sep = "─┼─".join("─" * w for w in col_widths)
            lines.append(sep)

    return "\n".join(lines)


def looks_truncated(text: str, truncated: bool = False) -> bool:
    """True when the provider hit the token cap or a fence was left open."""
    if truncated:
        return True
    return text.count("```") % 2 == 1 or text.count("~~~") % 2 == 1


def escape_html(text: str) -> str:
    """Escape text for safe embedding in Qt rich text."""
    return _html.escape(text, quote=False)


def render_inline_html(text: str) -> str:
    """Render inline markdown to HTML, escaping anything that is not markup.

    Code spans are handled before bold/italic/link tokens so their contents
    are never reinterpreted as markdown.
    """
    parts: list[str] = []
    last_end = 0

    for match in _INLINE_TOKEN.finditer(text):
        start, end = match.span()
        if start > last_end:
            parts.append(escape_html(text[last_end:start]))

        if match.group("code") is not None:
            parts.append(f'<code style="{_CODE_STYLE}">{escape_html(match.group("code"))}</code>')
        elif match.group("bold") is not None or match.group("bold2") is not None:
            inner = match.group("bold") or match.group("bold2") or ""
            parts.append(f"<strong>{render_inline_html(inner)}</strong>")
        elif match.group("italic") is not None:
            parts.append(f"<em>{render_inline_html(match.group('italic'))}</em>")
        elif match.group("linktext") is not None:
            url = match.group("linkurl") or ""
            label = match.group("linktext") or url
            if _SAFE_LINK.match(url):
                safe_url = _html.escape(url, quote=True)
                parts.append(
                    f'<a href="{safe_url}" style="color:#61AFEF; text-decoration:none;">'
                    f"{escape_html(label)}</a>"
                )
            else:
                parts.append(escape_html(label))

        last_end = end

    if last_end < len(text):
        parts.append(escape_html(text[last_end:]))

    return "".join(parts)


def render_text_html(text: str) -> str:
    """Render a prose block (headings, lists, quotes, paragraphs) to HTML."""
    out: list[str] = []
    paragraph: list[str] = []
    quote: list[str] = []
    list_kind: str | None = None

    def flush_paragraph() -> None:
        if paragraph:
            inner = "<br>".join(render_inline_html(line) for line in paragraph)
            out.append(f'<p style="{_BODY_STYLE}">{inner}</p>')
            paragraph.clear()

    def flush_quote() -> None:
        if quote:
            inner = "<br>".join(render_inline_html(line) for line in quote)
            out.append(
                '<blockquote style="margin:10px 0; padding:6px 12px; '
                'border-left:3px solid #61AFEF; color:#ABB2BF;">'
                f"{inner}</blockquote>"
            )
            quote.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    def open_list(kind: str) -> None:
        nonlocal list_kind
        if list_kind != kind:
            close_list()
            list_kind = kind
            style = "margin:6px 0 10px 18px; padding:0;"
            out.append(f'<{kind} style="{style}">')

    for raw in text.splitlines():
        line = raw.rstrip()

        if not line.strip():
            flush_paragraph()
            flush_quote()
            close_list()
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_quote()
            close_list()
            level = min(len(heading.group(1)), 6)
            size = {1: 18, 2: 16, 3: 15}.get(level, 14)
            out.append(
                f'<p style="margin:12px 0 8px 0; font-size:{size}px; font-weight:600; '
                f'color:#E5C07B;">{render_inline_html(heading.group(2))}</p>'
            )
            continue

        if _HR.match(line):
            flush_paragraph()
            flush_quote()
            close_list()
            out.append('<hr style="border:none; border-top:1px solid #3A3F4B; margin:12px 0;">')
            continue

        quoted = _QUOTE.match(line)
        if quoted:
            flush_paragraph()
            close_list()
            if quoted.group(1):
                quote.append(quoted.group(1))
            continue

        unordered = _UNORDERED.match(line)
        ordered = _ORDERED.match(line)
        if unordered or ordered:
            flush_paragraph()
            flush_quote()
            kind = "ul" if unordered else "ol"
            open_list(kind)
            item = (unordered or ordered).group(1)
            out.append(
                f'<li style="margin:2px 0;">{render_inline_html(item)}</li>'
            )
            continue

        flush_quote()
        close_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_quote()
    close_list()
    return "".join(out)


def render_table_html(rows: list[list[str]]) -> str:
    """Render table rows as an escaped HTML table."""
    if not rows:
        return ""

    cells_html: list[str] = []
    for index, row in enumerate(rows):
        tag = "th" if index == 0 else "td"
        weight = "600" if index == 0 else "400"
        background = "#2D3139" if index == 0 else "transparent"
        cells = "".join(
            f'<{tag} style="border:1px solid #3A3F4B; padding:6px 10px; '
            f'background-color:{background}; font-weight:{weight};">'
            f"{render_inline_html(cell)}</{tag}>"
            for cell in row
        )
        cells_html.append(f"<tr>{cells}</tr>")

    return (
        '<table style="border-collapse:collapse; width:100%; margin:10px 0; '
        'font-size:13px;">' + "".join(cells_html) + "</table>"
    )
