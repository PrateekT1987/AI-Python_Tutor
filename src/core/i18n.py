"""Internationalization (i18n) infrastructure using Qt's translation system."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator


class I18nManager:
    """Manages application translations."""

    def __init__(self, app: QCoreApplication):
        self.app = app
        self.translator = QTranslator()
        self.current_locale = QLocale.system().name()  # e.g., "en_US", "de_DE"

    def load_translations(self, locale: str | None = None) -> bool:
        """Load translation file for the given locale.

        Looks for `<locale>.qm` in the translations directory.
        Falls back to system locale if not specified.
        """
        if locale is not None:
            self.current_locale = locale

        # Translation files live in src/translations/
        trans_dir = Path(__file__).parent.parent / "ui" / "translations"
        filename = f"python_tutor_{self.current_locale}"

        if self.translator.load(filename, str(trans_dir)):
            self.app.installTranslator(self.translator)
            return True

        # Try without region (e.g., "de" instead of "de_DE")
        if "_" in self.current_locale:
            short = self.current_locale.split("_")[0]
            if self.translator.load(f"python_tutor_{short}", str(trans_dir)):
                self.app.installTranslator(self.translator)
                return True

        return False

    def set_locale(self, locale: str) -> bool:
        """Switch application language at runtime."""
        self.app.removeTranslator(self.translator)
        return self.load_translations(locale)


# Global instance (initialized in main.py)
i18n: I18nManager | None = None


def tr(context: str, text: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Translate a string using Qt's translation system.

    Wrapper around QCoreApplication.translate() for convenience.
    """
    return QCoreApplication.translate(context, text, disambiguation, n)


# Convenience function for use in non-QObject classes
def _(text: str) -> str:
    """Shorthand for tr() with default context."""
    return QCoreApplication.translate("PythonTutor", text)