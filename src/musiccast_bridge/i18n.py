"""Small explicit Polish/English catalog, independent of the Qt worker thread.

Polish is the source language. Language changes take effect at the next app
launch, so an active receiver connection never has to be rebuilt for translation.
Protocol events, device names and receiver metadata are intentionally unchanged.
"""

import json
from pathlib import Path

_language = "pl"
_english = json.loads(Path(__file__).with_name("en.json").read_text(encoding="utf-8"))


def set_language(language):
    global _language
    _language = "en" if language == "en" else "pl"


def language():
    return _language


def tr(text, **values):
    translated = _english.get(text, text) if _language == "en" else text
    return translated.format(**values) if values else translated


def install_qt_translations(application):
    """Translate Qt's own controls as well as application-owned labels."""
    import PySide6
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    previous = getattr(application, "_bridge_translator", None)
    if previous is not None:
        application.removeTranslator(previous)
        previous.deleteLater()
        application._bridge_translator = None
    QLocale.setDefault(QLocale("pl_PL" if language() == "pl" else "en_US"))
    if language() == "en":
        return True
    translator = QTranslator(application)
    candidates = (
        Path(__file__).with_name("qt_translations") / "qtbase_pl.qm",
        Path(PySide6.__file__).parent / "translations/qtbase_pl.qm",
        Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_pl.qm",
    )
    for candidate in candidates:
        if translator.load(str(candidate)):
            application.installTranslator(translator)
            application._bridge_translator = translator
            return True
    translator.deleteLater()
    return False
