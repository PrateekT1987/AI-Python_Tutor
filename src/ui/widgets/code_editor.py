"""Code editor with line-number gutter for the scratchpad."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import QPlainTextEdit, QWidget


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