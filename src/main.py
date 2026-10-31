#!/usr/bin/env python3
"""Python Tutor - Interactive Python learning with PyQt6."""

from __future__ import annotations

import os
import sys

# Silence Qt Wayland text-input debug spam (must be set before Qt is imported)
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland.textinput=false")

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.core.config import config
from src.ui.main_window import MainWindow
from src.ui.theme import apply_theme


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Python Tutor")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("PythonTutor")
    app.setOrganizationDomain("pythontutor.app")

    # One shared config instance: the UI and the request worker must agree on
    # the API key, endpoint and model.
    apply_theme(app)

    window = MainWindow(config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
