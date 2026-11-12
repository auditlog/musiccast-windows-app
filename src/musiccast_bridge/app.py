"""Desktop entry point; dependency errors remain visible when launched by double-click."""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from . import __version__
from .i18n import set_language, tr
from .settings import Settings, config_directory


def main():
    set_language(Settings.load().language)
    parser = argparse.ArgumentParser(description=tr("MusicCast Bridge — pilot i dźwięk z Windows"))
    parser.add_argument("--demo", action="store_true", help=tr("Uruchom przykładowy amplituner"))
    parser.add_argument("--host", help=tr("Adres IPv4 lub nazwa Yamahy"))
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--screenshot", help=argparse.SUPPRESS)
    args = parser.parse_args()
    from .installation import application_marker

    with application_marker():
        return _desktop(args)


def _desktop(args):
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print(
            tr("Brakuje PySide6. Uruchom install-windows.cmd, a następnie start-windows.cmd."),
            file=sys.stderr,
        )
        return 1
    from .ui import MainWindow, WindowLayoutError

    try:
        directory = config_directory()
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "musiccast.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8"
        )
        logging.basicConfig(
            level=logging.INFO,
            handlers=[handler],
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)
    application = QApplication(sys.argv[:1])
    set_language(Settings.load().language)
    application.setApplicationName("MusicCast Bridge")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("MusicCastBridge")
    application.setFont(QFont("Segoe UI", 10))
    try:
        window = MainWindow(demo=args.demo, host=args.host)
    except WindowLayoutError as error:
        QMessageBox.critical(None, tr("MusicCast Bridge — rozmiar okna"), str(error))
        return 1
    window.show()
    if args.screenshot:

        def capture():
            window.grab().save(args.screenshot)
            window._quit()

        QTimer.singleShot(1500, capture)
    return application.exec()
