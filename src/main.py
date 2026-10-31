#!/usr/bin/env python3
"""Python Tutor - Interactive Python learning with PyQt6."""

from __future__ import annotations

import os
import sys
import traceback

# Silence Qt Wayland text-input debug spam (must be set before Qt is imported)
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland.textinput=false")

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Configure logging BEFORE any other imports that might log
from src.core.logging_setup import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QLocale

from src.core.config import config
from src.core.i18n import I18nManager, i18n as i18n_module
from src.ui.main_window import MainWindow
from src.ui.theme import apply_theme


def _excepthook(exc_type, exc_value, exc_tb):
    """Global exception handler for uncaught exceptions."""
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
    # Show a user-friendly dialog if QApplication exists
    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(
            None,
            "Python Tutor - Fatal Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\n"
            f"Details have been logged to ~/.local/state/python-tutor/logs/python-tutor.log",
        )
    sys.exit(1)


def main() -> int:
    sys.excepthook = _excepthook

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Python Tutor")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("PythonTutor")
    app.setOrganizationDomain("pythontutor.app")

    # Initialize i18n (loads system locale translation if available)
    global i18n
    i18n = I18nManager(app)
    i18n.load_translations()

    # One shared config instance: the UI and the request worker must agree on
    # the API key, endpoint and model.
    apply_theme(app)

    log.info("Starting Python Tutor", version="2.0.0", locale=QLocale.system().name())
    window = MainWindow(config)
    window.show()

    exit_code = app.exec()
    log.info("Application exiting", exit_code=exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())