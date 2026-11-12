"""Compact native desktop remote, in Polish, with explicit connection/audio states."""

import asyncio
import sys
from concurrent.futures import InvalidStateError
from dataclasses import replace

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QKeySequence,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__, legal
from .audio import list_audio_devices
from .diagnostics import health_summary
from .discovery import discover_receivers
from .i18n import install_qt_translations, language, set_language, tr
from .installation import is_standard_cable_name
from .models import Snapshot, input_label
from .receiver import PLAYBACK_BITS, validate_host
from .settings import Settings
from .telemetry import TrafficMonitor, traffic_text
from .updates import UpdateInfo, check_for_updates, update_text
from .versioning import default_update_repository, github_repository
from .worker import Worker

STYLE = """
QWidget { background: #eef1f4; color: #182532; font-family: 'Segoe UI'; font-size: 10pt; }
QLabel { background: transparent; }
QLabel#title { font-size: 22pt; font-weight: 600; }
QLabel#subtitle, QLabel#hint { color: #526170; }
QLabel#section { font-size: 13pt; font-weight: 600; }
QLabel#volume { font-size: 34pt; font-weight: 600; color: #193f66; }
QLabel#status { font-weight: 600; color: #245e49; }
QLabel#notice { color: #7a311a; background: #fff0e9; padding: 0; border-radius: 6px; }
QFrame#panel { background: #ffffff; border-radius: 10px; }
QFrame#panel QLabel, QSlider { background: transparent; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #8998a6;
    border-radius: 5px; padding: 6px 8px; min-height: 20px; }
QComboBox QAbstractItemView { background: #ffffff; color: #182532;
    selection-background-color: #d4e5f5; }
QPushButton { background: #e1e8ef; border: 1px solid transparent; border-radius: 5px;
    padding: 6px 14px; min-height: 20px; font-weight: 600; }
QPushButton:hover { background: #d0dfed; }
QPushButton:pressed { background: #bed2e5; }
QPushButton#primary { background: #214f7c; color: white; }
QPushButton#primary:hover { background: #193e62; }
QPushButton:checked { background: #214f7c; color: white; }
QPushButton:disabled { color: #697786; background: #e2e6eb; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #286cac; }
QSlider::groove:horizontal { height: 6px; background: #c5d0db; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #285f94; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: #214f7c; border-radius: 9px; }
QSlider:disabled::handle:horizontal { background: #8494a5; }
QToolTip { background: #182532; color: white; border: none; padding: 6px; }
QLabel#notice[empty="true"] { background: transparent; }
"""

COMPACT_STYLE = """
QMainWindow QWidget { font-size: 9pt; }
QLabel#title { font-size: 18pt; }
QLabel#volume { font-size: 28pt; }
QMainWindow QPushButton { padding: 4px 10px; min-height: 18px; }
QMainWindow QLineEdit, QMainWindow QComboBox { padding: 4px 6px; min-height: 18px; }
"""


class WindowLayoutError(RuntimeError):
    """The available desktop cannot hold even the compact control layout."""


class BoundedLabel(QLabel):
    """Keep dynamic receiver text within a reserved slot; full text stays in its tooltip."""

    def __init__(self, text="", lines=2, name=None):
        super().__init__()
        self._full_text = ""
        self._lines = lines
        self._updating = False
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if name:
            self.setObjectName(name)
        if name == "notice":
            self.setContentsMargins(12, 12, 12, 12)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._update_display()

    def _update_display(self):
        if self._updating:
            return
        self._updating = True
        try:
            metrics = self.fontMetrics()
            margins = self.contentsMargins()
            self.setFixedHeight(
                metrics.lineSpacing() * self._lines + margins.top() + margins.bottom()
            )
            width = max(1, self.contentsRect().width())
            text = self._full_text.replace("\n", " ")
            utf16 = text.encode("utf-16-le")
            text_layout = QTextLayout(text, self.font())
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            text_layout.setTextOption(option)
            shown = []
            text_layout.beginLayout()
            for index in range(self._lines):
                line = text_layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                start = line.textStart()
                if index == self._lines - 1:
                    shown.append(
                        metrics.elidedText(
                            utf16[start * 2 :].decode("utf-16-le"),
                            Qt.TextElideMode.ElideRight,
                            width,
                        )
                    )
                else:
                    end = start + line.textLength()
                    shown.append(utf16[start * 2 : end * 2].decode("utf-16-le").rstrip())
            text_layout.endLayout()
            super().setText("\n".join(shown))
        finally:
            self._updating = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "_updating") and event.type() in {
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        }:
            self._update_display()


def label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def bounded_combo(name):
    widget = QComboBox()
    widget.setAccessibleName(name)
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(18)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    widget.currentTextChanged.connect(widget.setToolTip)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


class DiagnosticsDialog(QDialog):
    def __init__(self, report, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Diagnostyka AirPlay"))
        self._report = report
        self._last_report = None
        layout = QVBoxLayout(self)
        self.summary = BoundedLabel("", lines=2)
        layout.addWidget(self.summary)
        layout.addWidget(
            label(
                tr(
                    "Liczniki pokazują wysyłanie i żądania Yamahy. Odtworzenie każdej próbki "
                    "przez amplituner nie jest potwierdzane. "
                    "Techniczne nazwy zdarzeń i błędów w raporcie zachowują oryginalny język."
                ),
                "hint",
                wrap=True,
            )
        )
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setAccessibleName(tr("Bieżący raport diagnostyczny AirPlay"))
        self.output.setPlaceholderText(tr("Uruchom przesyłanie, aby rozpocząć diagnostykę."))
        self.output.setMaximumBlockCount(500)
        layout.addWidget(self.output)
        actions = QHBoxLayout()
        self.copy_button = button(tr("Kopiuj raport"), self._copy)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        actions.addWidget(button(tr("Zamknij"), self.close))
        layout.addLayout(actions)
        available = self.screen().availableGeometry()
        self.resize(min(860, available.width() - 40), min(540, available.height() - 80))
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._refresh)

    def showEvent(self, event):
        self._refresh()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def _refresh(self):
        report = self._report()
        self.summary.setText(health_summary(report))
        self.copy_button.setEnabled(bool(report))
        if report == self._last_report or self.output.textCursor().hasSelection():
            return
        scroll = self.output.verticalScrollBar()
        follow = scroll.value() == scroll.maximum()
        position = scroll.value()
        self.output.setPlainText(report)
        scroll.setValue(scroll.maximum() if follow else position)
        self._last_report = report

    def _copy(self):
        QApplication.clipboard().setText(self._report())
        self.copy_button.setText(tr("Skopiowano"))
        QTimer.singleShot(1800, lambda: self.copy_button.setText(tr("Kopiuj raport")))


class RoutingDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Dźwięk tylko na Yamasze"))
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        instructions = label(
            tr(
                '1. Zainstaluj <a href="https://vb-audio.com/Cable/">VB-CABLE</a> ze '
                "strony producenta i uruchom ponownie Windows.<br><br>2. W mikserze "
                "głośności Windows wybierz <b>CABLE Input</b> jako wyjście przeglądarki "
                "lub Spotify. Ustaw głośność tej aplikacji, odtwarzacza i wyjścia CABLE "
                "na 100%.<br><br>3. Odśwież wyjścia poniżej i wybierz kabel. Następnie w "
                "głównym oknie kliknij <b>Słuchaj z komputera</b>.<br><br>4. Głośniki "
                "komputera możesz teraz wyciszyć osobno. Głośność muzyki ustawiaj na "
                "Yamasze. CABLE pozostaw aktywny; wyłącz jego opcję „Nasłuchuj tego "
                "urządzenia”, jeśli jest włączona."
            ),
            wrap=True,
        )
        instructions.setOpenExternalLinks(True)
        instructions.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(instructions)
        self.status = label("", "hint", wrap=True)
        layout.addWidget(self.status)
        self.devices = bounded_combo(tr("Wirtualne wyjście do przesyłania na Yamahę"))
        layout.addWidget(self.devices)
        actions = QHBoxLayout()
        actions.addWidget(button(tr("Odśwież wyjścia"), parent._devices))
        self.choose = button(tr("Wybierz kabel"), self._choose)
        actions.addWidget(self.choose)
        actions.addStretch(1)
        actions.addWidget(button(tr("Zamknij"), self.close))
        layout.addLayout(actions)
        layout.addWidget(button(tr("Ustawienia…"), parent._show_settings))
        layout.addWidget(
            button(
                tr("Otwórz ustawienia dźwięku Windows"),
                lambda: QDesktopServices.openUrl(QUrl("ms-settings:sound")),
            )
        )
        self.setMinimumWidth(460)
        self.resize(
            min(610, self.screen().availableGeometry().width() - 40), self.sizeHint().height()
        )
        self.refresh_devices()

    def refresh_devices(self):
        self.devices.clear()
        source = self.parent().audio_device
        for index in range(source.count()):
            name, device = source.itemText(index), source.itemData(index)
            if (
                device is not None
                and device >= 0
                and "vb-audio" in name.casefold()
                and "cable" in name.casefold()
            ):
                self.devices.addItem(name, index)
        self.choose.setEnabled(self.devices.count() > 0 and not self.parent().settings.auto_output)
        self.status.setText(
            tr("Automatyczna trasa jest włączona. Docelowe wyjście zmień w Ustawieniach.")
            if self.parent().settings.auto_output else
            tr("Wybór kabla zostanie zapamiętany. Ustawienie wyjścia aplikacji wykonaj w Windows.")
            if self.devices.count()
            else tr("Nie znaleziono kabla VB-Audio. Po instalacji odśwież wyjścia.")
        )

    def _choose(self):
        parent = self.parent()
        if parent.settings.auto_output:
            parent._show_settings()
            return
        if parent.streaming or parent.audio_connecting:
            self.status.setText(tr("Zatrzymaj przesyłanie przed zmianą wyjścia."))
            return
        index = self.devices.currentData()
        if index is not None:
            parent.audio_device.setCurrentIndex(index)
            parent._select_audio_device(index)
            self.status.setText(tr("Wybrano kabel. W głównym oknie kliknij „Słuchaj z komputera”."))


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Ustawienia"))
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.tabs = tabs
        layout.addWidget(tabs)
        general = QWidget()
        form = QVBoxLayout(general)
        form.addWidget(label(tr("Język interfejsu")))
        self.language = QComboBox()
        self.language.setAccessibleName(tr("Język interfejsu"))
        self.language.addItem("Polski", "pl")
        self.language.addItem("English", "en")
        self.language.setCurrentIndex(self.language.findData(parent.settings.language))
        form.addWidget(self.language)
        form.addWidget(
            label(
                tr("Zmiana języka zostanie zastosowana po ponownym uruchomieniu."),
                "hint",
                wrap=True,
            )
        )
        self.tray_setting = QCheckBox(tr("Po zamknięciu pozostaw przy zegarze"))
        self.tray_setting.setChecked(parent.settings.close_to_tray)
        self.tray_setting.setEnabled(parent.tray is not None)
        form.addWidget(self.tray_setting)
        form.addWidget(
            label(
                tr(
                    "Zamknięcie do zasobnika nie kończy przesyłania. Zakończ aplikację przez "
                    "menu przy zegarze lub Ctrl+Q."
                ),
                "hint",
                wrap=True,
            )
        )
        form.addStretch(1)
        tabs.addTab(general, tr("Ogólne"))
        audio = QWidget()
        route = QVBoxLayout(audio)
        self.auto_output = QCheckBox(
            tr("Automatycznie przełączaj wyjście Windows podczas słuchania")
        )
        self.auto_output.setChecked(parent.settings.auto_output)
        self.auto_output.setEnabled(sys.platform == "win32")
        route.addWidget(self.auto_output)
        route.addWidget(label(tr("Wyjście Windows podczas słuchania"), wrap=True))
        self.outputs = bounded_combo(tr("Wyjście Windows podczas słuchania"))
        self.outputs.addItem(
            parent.settings.windows_output_name or tr("Wybierz wyjście…"),
            parent.settings.windows_output_id or None,
        )
        route.addWidget(self.outputs)
        self.output_refresh = button(tr("Odśwież wyjścia"), self._refresh)
        route.addWidget(self.output_refresh)
        route.addWidget(
            label(
                tr(
                    "Wybierz CABLE Input, aby słuchać tylko na Yamasze. Start zmieni domyślne"
                    " wyjście Windows; Stop lub zakończenie aplikacji przywróci poprzednie. "
                    "Ręczna zmiana wyjścia podczas słuchania zostanie zachowana. Wyjście "
                    "rozmów i mikrofon nie są zmieniane."
                ),
                "hint",
                wrap=True,
            )
        )
        route.addWidget(
            label(
                tr(
                    "Zmiana obejmuje aplikacje korzystające z domyślnego wyjścia Windows. "
                    "Jeśli przeglądarka lub Spotify ma osobne przypisanie w mikserze, ustaw "
                    "tam „Domyślne” albo CABLE Input. Głośność kabla i odtwarzacza ustaw na "
                    "100%."
                ),
                "hint",
                wrap=True,
            )
        )
        route.addWidget(
            button(
                tr("Otwórz mikser Windows"),
                lambda: QDesktopServices.openUrl(QUrl("ms-settings:apps-volume")),
            )
        )
        self.restore = button(tr("Przywróć wyjście"), self._restore)
        route.addWidget(self.restore)
        self.output_status = label("", "hint", wrap=True)
        route.addWidget(self.output_status)
        route.addStretch(1)
        tabs.addTab(audio, tr("Dźwięk Windows"))
        licenses = QWidget()
        texts = QVBoxLayout(licenses)
        texts.addWidget(
            label(
                tr(
                    "MusicCast Bridge — MIT. Qt/PySide6 — LGPLv3. VB-CABLE — osobne warunki "
                    "VB-Audio Software."
                ),
                wrap=True,
            )
        )
        self.documents = QComboBox()
        self.documents.setAccessibleName(tr("Licencje i zasady"))
        for caption, name in [
            (tr("Licencja MIT"), "LICENSE"),
            (tr("Zasady korzystania"), "TERMS.md"),
            (tr("Prywatność"), "PRIVACY.md"),
            (tr("Składniki zewnętrzne"), "THIRD_PARTY_NOTICES.md"),
        ]:
            self.documents.addItem(caption, name)
        if language() == "pl":
            self.documents.addItem(tr("MIT — oryginał angielski"), "LICENSE_ORIGINAL")
        texts.addWidget(self.documents)
        self.legal_text = QPlainTextEdit()
        self.legal_text.setReadOnly(True)
        self.legal_text.setAccessibleName(tr("Treść licencji lub zasad korzystania"))
        texts.addWidget(self.legal_text, 1)
        self.documents.currentIndexChanged.connect(self._document)
        self._document()
        texts.addWidget(
            button(
                tr("Oryginalne licencje bibliotek"),
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(legal.library_licenses()))),
            )
        )
        tabs.addTab(licenses, tr("Licencje i zasady"))
        self.updates_page = QWidget()
        updates = QVBoxLayout(self.updates_page)
        updates.addWidget(label(tr("Zainstalowana wersja: {version}", version=__version__)))
        self.check_updates = QCheckBox(tr("Sprawdzaj aktualizacje przy uruchamianiu"))
        self.check_updates.setChecked(parent.settings.check_updates_at_startup)
        updates.addWidget(self.check_updates)
        updates.addWidget(label(tr("Repozytorium GitHub")))
        self.repository = QLineEdit(parent.settings.update_repository)
        self.repository.setAccessibleName(tr("Repozytorium GitHub"))
        configured = default_update_repository()
        self.repository.setPlaceholderText(f"https://github.com/{configured}")
        updates.addWidget(self.repository)
        updates.addWidget(label(
            tr("Puste pole używa domyślnego adresu widocznego powyżej. "
               "Możesz wpisać inne repozytorium jako owner/repo lub pełny link GitHuba."),
            "hint", wrap=True,
        ))
        updates.addWidget(label(
            tr("Sprawdzanie łączy się z api.github.com. Wysyła adres IP i wersję aplikacji "
               "w nagłówku zapytania. Nowe wydanie pobierasz i instalujesz z jego strony. "
               "Sprawdzanie w tle nie przerywa odtwarzania."), "hint", wrap=True,
        ))
        self.update_status = label("", "hint", wrap=True)
        updates.addWidget(self.update_status)
        self.update_check = button(tr("Sprawdź teraz"), self._check_updates)
        updates.addWidget(self.update_check)
        self.open_release = button(tr("Otwórz wydanie na GitHubie"), self._open_release)
        updates.addWidget(self.open_release)
        updates.addStretch(1)
        tabs.addTab(self.updates_page, tr("Aktualizacje"))
        self.refresh_updates()
        self.status = label("", "hint", wrap=True)
        layout.addWidget(self.status)
        actions = QDialogButtonBox()
        actions.addButton(tr("Zapisz"), QDialogButtonBox.ButtonRole.AcceptRole)
        actions.addButton(tr("Anuluj"), QDialogButtonBox.ButtonRole.RejectRole)
        actions.accepted.connect(self._save)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        self.resize(min(650, self.screen().availableGeometry().width() - 40), 650)
        self._output_ids = set()
        self.refresh_enabled()
        if sys.platform == "win32":
            self._refresh()

    def refresh_enabled(self):
        idle = not self.parent().streaming and not self.parent().audio_connecting
        available = idle and sys.platform == "win32"
        self.auto_output.setEnabled(available)
        self.outputs.setEnabled(available)
        self.output_refresh.setEnabled(available and "windows_outputs" not in self.parent().pending)
        self.restore.setEnabled(
            available and "restore_output" not in self.parent().pending
            and self.parent().worker.session.output_route.path.exists()
        )

    def _refresh(self):
        self.output_status.setText(tr("Odczytywanie wyjść Windows…"))
        self.parent()._submit(
            "windows_outputs",
            asyncio.to_thread(self.parent().worker.session.output_route.backend.query),
        )
        self.refresh_enabled()

    def set_outputs(self, state):
        selected = self.outputs.currentData()
        self.outputs.clear()
        self.outputs.addItem(tr("Wybierz wyjście…"), None)
        self._output_ids = {item["id"] for item in state["devices"]}
        for item in state["devices"]:
            self.outputs.addItem(item["name"], item["id"])
        index = self.outputs.findData(selected)
        self.outputs.setCurrentIndex(max(0, index))
        current = next(
            (item["name"] for item in state["devices"] if item["id"] == state["defaults"].get("1")),
            "—",
        )
        self.output_status.setText(tr("Bieżące wyjście Windows: {name}", name=current))
        self.refresh_enabled()

    def _restore(self):
        self.parent()._submit(
            "restore_output", self.parent().worker.session.output_route.restore(recover=True)
        )

    def _document(self):
        try:
            self.legal_text.setPlainText(legal.document(self.documents.currentData()))
        except OSError:
            self.legal_text.setPlainText(
                tr("Brakuje dokumentu. Zainstaluj ponownie pełny pakiet aplikacji.")
            )

    def _save(self):
        parent = self.parent()
        repository = self.repository.text().strip()
        try:
            repository = github_repository(repository) if repository else ""
        except ValueError:
            self.status.setText(update_text(UpdateInfo("invalid_repository")))
            return
        changed_route = (self.auto_output.isChecked(), self.outputs.currentData()) != (
            parent.settings.auto_output,
            parent.settings.windows_output_id or None,
        )
        if changed_route and (parent.streaming or parent.audio_connecting):
            self.status.setText(tr("Zatrzymaj przesyłanie przed zmianą wyjścia."))
            return
        if (changed_route and self.auto_output.isChecked()
                and self.outputs.currentData() not in self._output_ids):
            self.status.setText(
                tr("Wybierz dostępne wyjście Windows lub wyłącz automatyczne przełączanie.")
            )
            return
        settings = replace(
            parent.settings,
            language=self.language.currentData(),
            close_to_tray=self.tray_setting.isChecked(),
            auto_output=self.auto_output.isChecked(),
            windows_output_id=self.outputs.currentData() or "",
            windows_output_name=self.outputs.currentText() if self.outputs.currentData() else "",
            check_updates_at_startup=self.check_updates.isChecked(),
            update_repository=repository,
        )
        try:
            settings.save()
        except OSError:
            self.status.setText(tr("Nie udało się zapisać ustawień. Spróbuj ponownie."))
            return
        changed_language = settings.language != parent.settings.language
        if settings.update_repository != parent.settings.update_repository:
            parent.update_info = UpdateInfo()
            parent.update_button.setText(tr("Aktualizacje…"))
        parent.settings = settings
        parent._notice(
            tr("Ustawienia zapisane. Zmiana języka wymaga ponownego uruchomienia.")
            if changed_language else tr("Ustawienia zapisane.")
        )
        parent._render()
        self.accept()

    def _check_updates(self):
        self.parent()._check_updates(self.repository.text())

    def _open_release(self):
        info = self.parent().update_info
        if info.state == "available" and info.release_url:
            QDesktopServices.openUrl(QUrl(info.release_url))

    def refresh_updates(self):
        info = self.parent().update_info
        self.update_status.setText(update_text(info))
        self.update_check.setEnabled("updates" not in self.parent().pending)
        self.open_release.setEnabled(info.state == "available" and bool(info.release_url))


class MainWindow(QMainWindow):
    def __init__(self, demo=False, host=None):
        super().__init__()
        self.setWindowTitle(f"MusicCast Bridge {__version__}")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.settings = Settings.load()
        set_language(self.settings.language)
        install_qt_translations(QApplication.instance())
        self.snapshot: Snapshot | None = None
        self.pending: set[str] = set()
        self.streaming = False
        self.audio_connecting = False
        self._closing = False
        self._airplay_dialog: QInputDialog | None = None
        self._diagnostics_window: DiagnosticsDialog | None = None
        self._routing_window: RoutingDialog | None = None
        self._settings_window: SettingsDialog | None = None
        self.update_info = UpdateInfo()
        self._update_repository_at_request = self.settings.update_repository
        self._device_missing = bool(
            self.settings.audio_device_name or self.settings.prefer_virtual_cable
        )
        self._allow_close = False
        self._connection_failed = False
        self.traffic_monitor = TrafficMonitor()
        self.worker = Worker(self)
        self.worker.result.connect(self._result)
        self.worker.failed.connect(self._failed)
        self.worker.audio_state.connect(self._audio_state)
        self.worker.airplay_secret.connect(self._show_airplay_prompt)
        self._build()
        self._render()
        try:
            self._fit_window()
        except WindowLayoutError:
            self.worker.loop.close()
            raise
        self._build_tray()
        self.worker.start()
        if not demo and self.worker.session.output_route.path.exists():
            self._notice(tr(
                "Pozostał zapis poprzedniej trasy dźwięku. W Ustawieniach kliknij "
                "„Przywróć wyjście” albo wybierz wyjście ręcznie w Windows."
            ))
        self.traffic_timer = QTimer(self)
        self.traffic_timer.setInterval(1000)
        self.traffic_timer.timeout.connect(self._refresh_traffic)
        self.traffic_timer.start()
        if self._device_missing and sys.platform == "win32" and not demo:
            QTimer.singleShot(0, self._devices)
        self.poll = QTimer(self)
        self.poll.setInterval(2000)
        self.poll.timeout.connect(self._poll)
        self.poll.start()
        if not demo and self.settings.check_updates_at_startup:
            QTimer.singleShot(1500, self._startup_update_check)
        if demo:
            QTimer.singleShot(0, self._connect_demo)
        elif host or self.settings.host:
            self.host.setText(host or self.settings.host)
            QTimer.singleShot(0, self._connect)

    def _build(self):
        root = QWidget()
        self.content = root
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(label("MusicCast Bridge", "title"))
        layout.addWidget(
            label(tr("Yamaha pod kontrolą. Dźwięk z komputera przez sieć."), "subtitle")
        )

        columns = QHBoxLayout()
        self.columns = columns
        columns.setSpacing(20)

        panel = QFrame()
        panel.setObjectName("panel")
        controls = QVBoxLayout(panel)
        self.receiver_layout = controls
        controls.setContentsMargins(16, 16, 16, 16)
        controls.setSpacing(12)
        header = QHBoxLayout()
        self.receiver_name = BoundedLabel(tr("Amplituner"), lines=1, name="section")
        header.addWidget(self.receiver_name, 1)
        self.power = button(tr("Włącz"), self._power)
        header.addWidget(self.power)
        controls.addLayout(header)
        self.volume_label = label("—", "volume")
        self.volume_label.setAccessibleName(tr("Aktualna głośność"))
        volume_readout = QHBoxLayout()
        volume_readout.addWidget(self.volume_label)
        self.volume_hint = BoundedLabel(tr("Głośność amplitunera"), name="hint")
        volume_readout.addWidget(self.volume_hint, 1)
        self.mute = button(tr("Wycisz"), self._mute)
        self.mute.setMinimumWidth(
            self.mute.fontMetrics().horizontalAdvance(tr("Przywróć dźwięk")) + 34
        )
        volume_readout.addWidget(self.mute)
        controls.addLayout(volume_readout)
        volume_row = QHBoxLayout()
        self.volume_down = button(tr("Ciszej"), lambda: self._step_volume(-1))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setAccessibleName(tr("Głośność amplitunera w procentach zakresu"))
        self.volume.sliderReleased.connect(self._set_volume)
        self.volume.valueChanged.connect(self._volume_preview)
        self.volume.actionTriggered.connect(lambda action: self._schedule_volume())
        self.volume_timer = QTimer(self)
        self.volume_timer.setSingleShot(True)
        self.volume_timer.setInterval(250)
        self.volume_timer.timeout.connect(self._set_volume)
        self.volume_up = button(tr("Głośniej"), lambda: self._step_volume(1))
        volume_row.addWidget(self.volume_down)
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_up)
        controls.addLayout(volume_row)
        source_row = QHBoxLayout()
        source_row.addWidget(label(tr("Źródło")))
        self.source = bounded_combo(tr("Źródło dźwięku amplitunera"))
        self.source.activated.connect(self._input)
        source_row.addWidget(self.source, 1)
        controls.addLayout(source_row)
        self.track = BoundedLabel()
        controls.addWidget(self.track)
        transport = QHBoxLayout()
        self.playback_buttons = {}
        for action, text in [
            ("previous", tr("Poprzedni")),
            ("play", tr("Odtwórz")),
            ("pause", tr("Pauza")),
            ("stop", tr("Zatrzymaj")),
            ("next", tr("Następny")),
        ]:
            widget = button(text, lambda checked=False, a=action: self._command("playback", a))
            self.playback_buttons[action] = widget
            transport.addWidget(widget)
        controls.addLayout(transport)
        traffic = QGridLayout()
        traffic.setHorizontalSpacing(10)
        traffic.setVerticalSpacing(4)
        traffic.setColumnStretch(1, 1)
        traffic.addWidget(label(tr("Transmisja"), "section"), 0, 0)
        self.traffic_state = BoundedLabel(tr("Nieaktywna"), lines=1, name="hint")
        traffic.addWidget(self.traffic_state, 0, 1)
        self.traffic_values = {}
        self.traffic_hints = {
            "audio": tr(
                "Bieżący ruch RTP audio i liczba pakietów na sekundę. Bez nagłówków "
                "UDP/IP i ruchu innych aplikacji."
            ),
            "resends": tr(
                "Bieżący ruch powtórzeń i ich liczba w tej próbie połączenia. Przekazanie"
                " do UDP nie potwierdza odbioru przez Yamahę."
            ),
            "buffer": tr(
                "Ilość dźwięku w buforze źródła i cisza dodana przy braku danych. To nie "
                "jest całkowite opóźnienie odsłuchu."
            ),
            "errors": tr(
                "Żądane powtórzenia niedostępne w buforze oraz błędy ich wysyłania. "
                "Liczniki obejmują bieżącą próbę połączenia."
            ),
            "gap": tr(
                "Najdłuższa przerwa między wysłaniami audio od początku próby. To nie "
                "jest czas dotarcia pakietu do Yamahy."
            ),
        }
        for row, (key, title) in enumerate(
            [
                ("audio", "Audio"),
                ("resends", tr("Powtórzenia")),
                ("buffer", tr("Bufor / dodana cisza")),
                ("errors", tr("Błędy powtórzeń")),
                ("gap", tr("Przerwa nadajnika")),
            ],
            start=1,
        ):
            caption = label(title, "hint")
            caption.setToolTip(self.traffic_hints[key])
            value = BoundedLabel("—", lines=1)
            value.setAccessibleName(title)
            traffic.addWidget(caption, row, 0)
            traffic.addWidget(value, row, 1)
            self.traffic_values[key] = value
        capacity = label(tr("Dostępne pasmo: niezmierzone"), "hint")
        capacity.setToolTip(
            tr(
                "Ruch aplikacji nie określa wolnej przepustowości łącza. Ten podgląd nie "
                "wykonuje testu obciążającego sieć."
            )
        )
        traffic.addWidget(capacity, 6, 0, 1, 2)
        controls.addLayout(traffic)
        controls.addStretch(1)
        columns.addWidget(panel, 11)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        connection_header = QHBoxLayout()
        connection_header.addWidget(label(tr("Połączenie"), "section"))
        self.connection_status = BoundedLabel(tr("Nie połączono"), name="status")
        connection_header.addWidget(self.connection_status, 1)
        right_layout.addLayout(connection_header)

        connect_row = QHBoxLayout()
        self.host = QLineEdit()
        self.host.setPlaceholderText(tr("Adres IP lub nazwa Yamahy"))
        self.host.setAccessibleName(tr("Adres IP lub nazwa amplitunera"))
        self.host.returnPressed.connect(self._connect)
        self.connect_button = button(tr("Połącz"), self._connect, primary=True)
        self.search_button = button(tr("Szukaj"), self._discover)
        self.connect_button.setMinimumWidth(
            self.connect_button.fontMetrics().horizontalAdvance(tr("Łączenie…")) + 34
        )
        self.search_button.setMinimumWidth(
            self.search_button.fontMetrics().horizontalAdvance(tr("Szukanie…")) + 34
        )
        connect_row.addWidget(self.host, 1)
        connect_row.addWidget(self.connect_button)
        connect_row.addWidget(self.search_button)
        right_layout.addLayout(connect_row)

        discovery_row = QHBoxLayout()
        self.found = bounded_combo(tr("Amplitunery znalezione w sieci"))
        self.found.setPlaceholderText(tr("Znalezione amplitunery"))
        self.found.currentIndexChanged.connect(lambda index: self._render())
        self.use_ip = button(tr("Użyj IP"), self._choose_found)
        self.use_ip.setToolTip(tr("Wpisz IP wybranej Yamahy do pola połączenia"))
        discovery_row.addWidget(self.found, 1)
        discovery_row.addWidget(self.use_ip)
        right_layout.addLayout(discovery_row)

        right_layout.addSpacing(12)
        right_layout.addWidget(label(tr("Dźwięk z komputera"), "section"))
        self.audio_hint = label(
            tr(
                "AirPlay przesyła dźwięk przeglądarki i innych aplikacji. Obraz na PC "
                "może wyprzedzać dźwięk."
            ),
            "hint",
            wrap=True,
        )
        self.audio_hint.setToolTip(self.audio_hint.text())
        right_layout.addWidget(self.audio_hint)
        device_row = QHBoxLayout()
        self.audio_device = bounded_combo(tr("Wyjście Windows do przechwycenia"))
        self.audio_device.addItem(tr("Domyślne wyjście Windows"), None)
        if self._device_missing:
            target = self.settings.audio_device_name or "VB-CABLE"
            self.audio_device.addItem(tr("Sprawdzanie: {v0}", v0=target), -1)
            self.audio_device.setCurrentIndex(1)
        self.audio_device.activated.connect(self._select_audio_device)
        self.devices_button = button(tr("Odśwież wyjścia"), self._devices)
        device_row.addWidget(self.audio_device, 1)
        device_row.addWidget(self.devices_button)
        right_layout.addLayout(device_row)
        audio_row = QHBoxLayout()
        self.audio_button = button(tr("Słuchaj z komputera"), self._start_audio, primary=True)
        self.audio_stop = button(tr("Zatrzymaj przesyłanie"), self._stop_audio)
        self.file_button = button(tr("Test pliku…"), self._file)
        audio_row.addWidget(self.audio_button, 1)
        audio_row.addWidget(self.audio_stop)
        right_layout.addLayout(audio_row)
        file_row = QHBoxLayout()
        self.audio_status = BoundedLabel(tr("Przesyłanie zatrzymane"), name="hint")
        file_row.addWidget(self.file_button)
        self.routing_button = button(tr("Tylko Yamaha…"), self._show_routing)
        file_row.addWidget(self.routing_button)
        file_row.addWidget(self.audio_status, 1)
        right_layout.addLayout(file_row)
        self.routing_hint = BoundedLabel(
            tr(
                "Wyjście Windows pozostaje aktywne. Wirtualny kabel audio pozwala słyszeć"
                " tylko Yamahę."
            ),
            name="hint",
            lines=3,
        )
        self.routing_hint.setToolTip(self.routing_hint.text())
        right_layout.addWidget(self.routing_hint)
        right_layout.addStretch(1)
        columns.addWidget(right, 10)
        layout.addLayout(columns)

        self.notice = BoundedLabel("", name="notice")
        self.notice.setProperty("empty", True)
        layout.addWidget(self.notice)
        footer = QHBoxLayout()
        self.settings_button = button(tr("Ustawienia…"), self._show_settings)
        footer.addWidget(self.settings_button)
        self.update_button = button(tr("Aktualizacje…"), self._show_updates)
        footer.addWidget(self.update_button)
        footer.addStretch(1)
        self.diagnostics_button = button(tr("Diagnostyka…"), self._show_diagnostics)
        footer.addWidget(self.diagnostics_button)
        self.demo_button = button(tr("Tryb demonstracyjny"), self._connect_demo)
        footer.addWidget(self.demo_button)
        layout.addLayout(footer)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)
        focus_order = [
            self.host,
            self.connect_button,
            self.search_button,
            self.found,
            self.use_ip,
            self.power,
            self.volume_down,
            self.volume,
            self.volume_up,
            self.mute,
            self.source,
            *self.playback_buttons.values(),
            self.audio_device,
            self.devices_button,
            self.audio_button,
            self.audio_stop,
            self.file_button,
            self.routing_button,
            self.settings_button,
            self.update_button,
            self.diagnostics_button,
            self.demo_button,
        ]
        for first, second in zip(focus_order, focus_order[1:], strict=False):
            QWidget.setTabOrder(first, second)

    def _fit_window(self, available=None):
        """Measure once with the actual Qt font/DPI, then keep the window fixed."""
        if available is None:
            available = self.screen().availableGeometry()
        width = min(1080, available.width() - 24)
        frame_height = self.style().pixelMetric(QStyle.PixelMetric.PM_TitleBarHeight) + 16
        for compact in (False, True):
            self.setStyleSheet(STYLE + (COMPACT_STYLE if compact else ""))
            self.content.layout().setContentsMargins(
                16 if compact else 20,
                12 if compact else 16,
                16 if compact else 20,
                12 if compact else 16,
            )
            self.content.layout().setSpacing(8 if compact else 12)
            self.columns.setSpacing(12 if compact else 20)
            inset = 12 if compact else 16
            self.receiver_layout.setContentsMargins(inset, inset, inset, inset)
            self.receiver_layout.setSpacing(8 if compact else 12)
            self.audio_hint.setText(
                tr("AirPlay: dźwięk z PC z opóźnieniem.") if compact else self.audio_hint.toolTip()
            )
            self.ensurePolished()
            for widget in self.content.findChildren(QWidget):
                widget.ensurePolished()
                if isinstance(widget, BoundedLabel):
                    widget._update_display()
            self.resize(width, available.height())
            self.content.layout().activate()
            measured = self.content.layout().totalHeightForWidth(width)
            if measured < 0:
                measured = self.content.sizeHint().height()
            height = max(measured, self.content.minimumSizeHint().height())
            minimum_width = self.content.minimumSizeHint().width()
            if minimum_width <= width and height <= available.height() - frame_height:
                break
        width = max(width, minimum_width)
        if width > available.width() - 24 or height > available.height() - frame_height:
            raise WindowLayoutError(
                tr(
                    "Obszar pulpitu jest za mały, aby wyświetlić wszystkie przyciski bez "
                    "przewijania. Układ wymaga {v0}×{v1} px logicznych; obszar roboczy ma "
                    "{v2}×{v3} px. Zmniejsz skalowanie Windows lub zwiększ rozdzielczość "
                    "ekranu.",
                    v0=width,
                    v1=height + frame_height,
                    v2=available.width(),
                    v3=available.height(),
                )
            )
        self.setFixedSize(width, height)

    def _build_tray(self):
        self.tray = None
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        self.setWindowIcon(icon)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("MusicCast Bridge")
            menu = QMenu(self)
            menu.addAction(tr("Otwórz"), self._show)
            menu.addAction(tr("Zatrzymaj dźwięk"), self._stop_audio)
            menu.addSeparator()
            menu.addAction(tr("Zakończ"), self._quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(
                lambda reason: (
                    self._show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
                )
            )
            self.tray.show()
        else:
            pass
        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self._quit)
        self.addAction(quit_action)

    def _show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _submit(self, tag, coroutine):
        if tag in self.pending or self._closing:
            coroutine.close()
            return
        self.pending.add(tag)
        self.worker.submit(tag, coroutine)
        self._render()

    def _notice(self, text):
        self.notice.setText(text)
        self.notice.setProperty("empty", not bool(text))
        self.notice.style().unpolish(self.notice)
        self.notice.style().polish(self.notice)
        self.notice.update()

    def _connect(self):
        try:
            host = validate_host(self.host.text())
        except ValueError as error:
            self._notice(str(error))
            return
        self.volume_timer.stop()
        self.snapshot = None
        self._notice("")
        self._connection_failed = False
        self._submit("connect", self.worker.session.connect(host))

    def _connect_demo(self):
        self.snapshot = None
        self._notice(
            tr("Tryb demonstracyjny — dane są przykładowe; żadne urządzenie nie jest sterowane.")
        )
        self._submit("connect", self.worker.session.connect("demo.local", demo=True))

    def _discover(self):
        self._submit("discover", discover_receivers())

    def _choose_found(self):
        address = self.found.currentData()
        if self.host.isEnabled() and isinstance(address, str) and address:
            self.host.setText(address)
            self.host.setFocus()
            self.host.selectAll()

    def _poll(self):
        if self.snapshot and not self.pending and not self.volume.isSliderDown():
            self._submit("refresh", self.worker.session.refresh())

    def _command(self, method, value):
        if self.snapshot:
            self._notice(
                ""
                if not self.snapshot.demo
                else tr("Tryb demonstracyjny — zmiany dotyczą tylko danych przykładowych.")
            )
            self._submit("command", self.worker.session.command(method, value))

    def _power(self):
        if self.snapshot:
            self._command("set_power", "standby" if self.snapshot.status.power == "on" else "on")

    def _mute(self):
        if self.snapshot:
            self._command("set_mute", not self.snapshot.status.mute)

    def _step_volume(self, change):
        self._command("step_volume", change)

    def _schedule_volume(self):
        if not self.volume.isSliderDown():
            QTimer.singleShot(0, self.volume_timer.start)

    def _volume_preview(self, value):
        if self.volume.isSliderDown():
            self.volume_hint.setText(tr("Wybrany poziom: {v0}% zakresu amplitunera", v0=value))

    def _set_volume(self):
        if self.volume.isEnabled():
            self._command("set_volume", self.volume.value())

    def _input(self, index):
        self._command("set_input", self.source.itemData(index))

    def _devices(self):
        self._submit("devices", asyncio.to_thread(list_audio_devices))

    def _select_audio_device(self, index):
        device = self.audio_device.itemData(index)
        if device is not None and device < 0:
            return
        self._device_missing = False
        self.settings.prefer_virtual_cable = False
        self.settings.audio_device_name = (
            self.audio_device.itemText(index) if device is not None else ""
        )
        try:
            self.settings.save()
        except OSError:
            self._notice(tr("Nie udało się zapisać wyjścia dźwięku."))
        self._render()

    def _start_audio(self):
        if self._device_missing and not self.settings.auto_output:
            self._notice(
                tr("Zapamiętane wyjście jest niedostępne. Odśwież wyjścia lub wybierz inne.")
            )
            return
        self._notice("")
        self.audio_connecting = True
        if self.settings.auto_output:
            if not self.settings.windows_output_id:
                self.audio_connecting = False
                self._notice(tr("Wybierz wyjście Windows w ustawieniach aplikacji."))
                return
            self._submit(
                "start",
                self.worker.session.start_audio(route_output_id=self.settings.windows_output_id),
            )
        else:
            self._submit("start", self.worker.session.start_audio(self.audio_device.currentData()))

    def _file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz plik do testu AirPlay"), "", tr("Dźwięk (*.wav *.flac *.mp3 *.ogg)"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            self._notice("")
            self.audio_connecting = True
            self._submit("start", self.worker.session.start_audio(filename=filename))

    def _stop_audio(self):
        self._submit("stop", self.worker.session.stop_audio())

    def _show_diagnostics(self):
        if self._diagnostics_window is None:
            self._diagnostics_window = DiagnosticsDialog(
                self.worker.session.audio.diagnostics.report, self
            )
        self._diagnostics_window.show()
        self._diagnostics_window.raise_()
        self._diagnostics_window.activateWindow()

    def _refresh_traffic(self, now=None):
        if self._closing:
            return
        view = self.traffic_monitor.sample(self.worker.session.audio.diagnostics.snapshot(), now)
        self.traffic_state.setText(view.state)
        for name, text in traffic_text(view).items():
            self.traffic_values[name].setText(text)
            self.traffic_values[name].setToolTip(f"{text}\n{self.traffic_hints[name]}")

    def _show_routing(self):
        if self._routing_window is None:
            self._routing_window = RoutingDialog(self)
        self._routing_window.refresh_devices()
        self._routing_window.show()
        self._routing_window.raise_()
        self._routing_window.activateWindow()
        if sys.platform == "win32" and not self.streaming and not self.audio_connecting:
            self._devices()

    def _show_settings(self):
        if self._settings_window is None or not self._settings_window.isVisible():
            if self._settings_window is not None:
                self._settings_window.deleteLater()
            self._settings_window = SettingsDialog(self)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _show_updates(self):
        self._show_settings()
        self._settings_window.tabs.setCurrentWidget(self._settings_window.updates_page)

    def _check_updates(self, repository=None):
        if self._closing or "updates" in self.pending:
            return
        repository = self.settings.update_repository if repository is None else repository
        self._update_repository_at_request = self.settings.update_repository
        self.update_info = UpdateInfo("checking")
        self._submit("updates", asyncio.to_thread(check_for_updates, repository))
        if self._settings_window is not None:
            self._settings_window.refresh_updates()

    def _startup_update_check(self):
        if self.settings.check_updates_at_startup:
            self._check_updates()

    def _result(self, tag, result):
        self.pending.discard(tag)
        if tag == "updates":
            if self._update_repository_at_request != self.settings.update_repository:
                self.update_info = UpdateInfo()
            elif isinstance(result, UpdateInfo):
                self.update_info = result
            self.update_button.setText(
                tr("Nowa wersja!") if self.update_info.state == "available" else tr("Aktualizacje…")
            )
            if self._settings_window is not None:
                self._settings_window.refresh_updates()
        if tag == "windows_outputs" and self._settings_window is not None:
            self._settings_window.set_outputs(result)
        elif tag == "restore_output":
            self._notice(
                tr("Przywrócono poprzednie wyjście lub zachowano ręczną zmianę użytkownika.")
            )
        if isinstance(result, Snapshot):
            recovered = self._connection_failed
            self.snapshot = result
            self._connection_failed = False
            if recovered and not result.demo:
                self._notice("")
            if tag == "connect" and not result.demo:
                self.settings.host = result.host
                try:
                    self.settings.save()
                except OSError:
                    self._notice(tr("Połączono, ale nie udało się zapisać adresu amplitunera."))
        elif tag == "discover":
            self.found.clear()
            for item in result:
                self.found.addItem(f"{item.name} — {item.host}", item.host)
            if not result:
                self._notice(
                    tr("Nie znaleziono Yamahy. Wpisz jej adres IP z menu Network → Information.")
                )
        elif tag == "devices":
            self.audio_device.clear()
            self.audio_device.addItem(tr("Domyślne wyjście Windows"), None)
            for item in result:
                self.audio_device.addItem(item.name, item.index)
            name = self.settings.audio_device_name
            matches = (
                [
                    index
                    for index in range(1, self.audio_device.count())
                    if self.audio_device.itemText(index) == name
                ]
                if name
                else []
            )
            if not name and self.settings.prefer_virtual_cable:
                matches = [
                    index
                    for index in range(1, self.audio_device.count())
                    if is_standard_cable_name(self.audio_device.itemText(index))
                ]
            self._device_missing = (
                bool(name or self.settings.prefer_virtual_cable) and len(matches) != 1
            )
            if len(matches) == 1:
                self.audio_device.setCurrentIndex(matches[0])
                if self.settings.prefer_virtual_cable:
                    self._select_audio_device(matches[0])
            elif self._device_missing:
                self.audio_device.addItem(tr("Wybierz wyjście: {v0}", v0=name or "VB-CABLE"), -1)
                self.audio_device.setCurrentIndex(self.audio_device.count() - 1)
                self._notice(tr("Zapamiętane wyjście jest niedostępne. Wybierz wyjście ręcznie."))
            if self._routing_window is not None:
                self._routing_window.refresh_devices()
        self._render()

    def _failed(self, tag, text):
        self.pending.discard(tag)
        if tag == "updates":
            self.update_info = UpdateInfo("unreachable")
            self.update_button.setText(tr("Aktualizacje…"))
            if self._settings_window is not None:
                self._settings_window.refresh_updates()
            self._render()
            return
        self._notice(text)
        if tag in {"windows_outputs", "restore_output"} and self._settings_window is not None:
            self._settings_window.output_status.setText(text)
        if tag in {"connect", "refresh"}:
            self._connection_failed = True
        self._render()

    @Slot(str, str)
    def _audio_state(self, state, text):
        if state == "stopped" and self._airplay_dialog is not None:
            self._airplay_dialog.reject()
        self.streaming = state == "playing"
        self.audio_connecting = state in {"preparing", "connecting"}
        if state == "error":
            self._notice(text)
        self.audio_status.setText(text)
        self._render()

    @Slot(str, str, object)
    def _show_airplay_prompt(self, title, message, reply):
        if self._closing or reply.done():
            reply.cancel()
            return
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(message)
        dialog.setTextEchoMode(QLineEdit.EchoMode.Password)
        dialog.setOkButtonText(tr("Dalej"))
        dialog.setCancelButtonText(tr("Anuluj"))
        self._airplay_dialog = dialog

        def finish(result):
            self._airplay_dialog = None
            try:
                reply.set_result(
                    dialog.textValue() if result == QDialog.DialogCode.Accepted else None
                )
            except InvalidStateError:
                pass  # The stream was stopped while the dialog was open.
            dialog.deleteLater()

        dialog.finished.connect(finish)
        dialog.open()

    def _render(self):
        busy = bool(self.pending - {"refresh", "discover", "devices", "windows_outputs", "updates"})
        connecting = "connect" in self.pending
        snapshot = self.snapshot
        usable = bool(snapshot) and not self._connection_failed and not connecting
        self.connect_button.setText(tr("Łączenie…") if connecting else tr("Połącz"))
        self.connect_button.setEnabled(not busy)
        self.host.setEnabled(not busy)
        self.demo_button.setEnabled(not busy)
        self.search_button.setText(tr("Szukanie…") if "discover" in self.pending else tr("Szukaj"))
        self.search_button.setEnabled("discover" not in self.pending and not busy)
        self.found.setEnabled(not busy)
        self.use_ip.setEnabled(not busy and bool(self.found.currentData()))
        self.connection_status.setText(
            tr("Łączenie z amplitunerem…")
            if connecting
            else tr("Utracono połączenie — sprawdzam ponownie…")
            if self._connection_failed and snapshot
            else tr("Nie połączono")
            if not snapshot
            else tr("Tryb demonstracyjny")
            if snapshot.demo
            else tr("Połączono · {v0}", v0=snapshot.host)
        )
        caps = snapshot.capabilities if snapshot else None
        state = snapshot.status if snapshot else None
        on = bool(state and state.power == "on")
        self.receiver_name.setText(snapshot.model if snapshot else tr("Amplituner"))
        self.power.setText(tr("Do czuwania") if on else tr("Włącz"))
        self.power.setEnabled(usable and not busy and "power" in caps.functions)
        flags = state.disable_flags if state else 0
        volume_ok = (
            usable and on and not busy and not self.audio_connecting and caps.volume is not None
        )
        self.volume.setEnabled(volume_ok and "volume" in caps.functions and not flags & 1)
        self.volume_down.setEnabled(self.volume.isEnabled())
        self.volume_up.setEnabled(self.volume.isEnabled())
        self.mute.setEnabled(
            usable and on and not busy and "mute" in caps.functions and not flags & 2
        )
        self.mute.setText(tr("Przywróć dźwięk") if state and state.mute else tr("Wycisz"))
        self.source.setEnabled(usable and on and not busy and not self.audio_connecting)
        if snapshot:
            ids = [self.source.itemData(i) for i in range(self.source.count())]
            if ids != list(caps.inputs):
                self.source.blockSignals(True)
                self.source.clear()
                for input_id in caps.inputs:
                    self.source.addItem(
                        snapshot.input_names.get(input_id, input_label(input_id)), input_id
                    )
                self.source.blockSignals(False)
            self.source.setCurrentIndex(self.source.findData(state.input))
            if caps.volume and state.volume is not None:
                percent = caps.volume.to_percent(state.volume)
                ceiling = (
                    caps.volume.to_percent(state.max_volume)
                    if state.max_volume is not None
                    else 100
                )
                if not self.volume.isSliderDown() and not self.volume_timer.isActive() and not busy:
                    self.volume.blockSignals(True)
                    self.volume.setMaximum(ceiling)
                    self.volume.setValue(percent)
                    self.volume.blockSignals(False)
                self.volume_label.setText(state.volume_display or f"{percent}%")
                if not self.volume.isSliderDown():
                    self.volume_hint.setText(
                        tr("Wyciszono")
                        if state.mute
                        else tr("Amplituner w czuwaniu")
                        if not on
                        else tr("{v0}% zakresu amplitunera", v0=percent)
                    )
            else:
                self.volume_label.setText("—")
            title = snapshot.play_info.get("track", "")
            artist = snapshot.play_info.get("artist", "")
            self.track.setText(
                " · ".join(str(part) for part in (title, artist) if part)
                or input_label(state.input)
            )
        else:
            self.volume_label.setText("—")
            self.track.setText(tr("Połącz amplituner, aby wybrać źródło i sterować odtwarzaniem."))
            self.source.clear()
        attributes = int(snapshot.play_info.get("attribute", 0)) if snapshot else 0
        for action, widget in self.playback_buttons.items():
            widget.setEnabled(
                usable
                and on
                and not busy
                and not self.streaming
                and bool(attributes & (1 << PLAYBACK_BITS[action]))
            )
        can_audio = usable and not snapshot.demo and "airplay" in caps.inputs if snapshot else False
        self.audio_button.setEnabled(
            can_audio
            and sys.platform == "win32"
            and (self.settings.auto_output or not self._device_missing)
            and not busy
            and not self.streaming
            and not self.audio_connecting
        )
        self.file_button.setEnabled(
            can_audio and not busy and not self.streaming and not self.audio_connecting
        )
        self.audio_stop.setEnabled(
            (self.streaming or self.audio_connecting) and "stop" not in self.pending
        )
        self.audio_device.setEnabled(
            not self.streaming and not self.audio_connecting and not self.settings.auto_output
        )
        self.routing_hint.setText(
            tr("Pozostał zapis poprzedniej trasy dźwięku. W Ustawieniach kliknij "
               "„Przywróć wyjście” albo wybierz wyjście ręcznie w Windows.")
            if (not self.streaming and not self.audio_connecting
                and self.worker.session.output_route.path.exists()) else
            tr(
                "Wyjście Windows: {name}. Start przełączy dźwięk systemu; "
                "Stop przywróci poprzednie wyjście.",
                name=self.settings.windows_output_name or "—",
            )
            if self.settings.auto_output
            else tr(
                "Aby słuchać tylko na Yamasze, wybierz CABLE Input w mikserze Windows "
                "albo włącz automatyczne przełączanie w Ustawieniach."
            )
        )
        if self._settings_window is not None:
            self._settings_window.refresh_enabled()
        self.devices_button.setEnabled(
            sys.platform == "win32"
            and "devices" not in self.pending
            and not self.streaming
            and not self.audio_connecting
        )
        if sys.platform != "win32" and not self.streaming and not self.audio_connecting:
            self.audio_status.setText(
                tr("Sterowanie działa tutaj; przechwytywanie dźwięku uruchom w Windows.")
            )

    def _quit(self):
        if self._closing:
            return
        self._closing = True
        self.poll.stop()
        self.traffic_timer.stop()
        self.setEnabled(False)
        try:
            self.settings.save()
        except OSError:
            pass
        if self.tray:
            self.tray.hide()
        self.worker.finished.connect(self._finished)
        self.worker.shutdown()

    def _finished(self):
        self._allow_close = True
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent):
        if self._allow_close:
            event.accept()
        elif self.tray and self.settings.close_to_tray and not self._closing:
            self.hide()
            event.ignore()
        else:
            self._quit()
            event.ignore()
