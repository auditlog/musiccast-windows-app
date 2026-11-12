"""Runs with the real Qt runtime on Windows; skipped when Qt is not installed."""

import os
import sys
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

from musiccast_bridge.audio import AudioDevice
from musiccast_bridge.demo import demo_receiver
from musiccast_bridge.discovery import DiscoveredReceiver
from musiccast_bridge.i18n import set_language
from musiccast_bridge.settings import Settings
from musiccast_bridge.updates import UpdateInfo

# Qt's Windows offscreen plugin uses a FreeType font database instead of the
# system font database. Use the production backend on Windows; Linux CI stays
# headless, and an explicit platform override is still respected.
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
try:
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QScrollArea, QWidget

    from musiccast_bridge.ui import BoundedLabel, MainWindow, WindowLayoutError
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "Qt dependencies unavailable in this environment")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        if sys.platform == "win32" and "Segoe UI" not in QFontDatabase.families():
            raise RuntimeError(
                "Qt nie widzi systemowej czcionki Segoe UI. "
                f"Platforma Qt: {cls.application.platformName()}. "
                "Dla testów Windows użyj QT_QPA_PLATFORM=windows."
            )
        cls.application.setFont(QFont("Segoe UI", 10))
        print(
            f"Qt UI tests: platform={cls.application.platformName()}, "
            f"font={cls.application.font().family()} {cls.application.font().pointSize()}pt",
            file=sys.stderr,
        )

    def setUp(self):
        locale = "en" if self._testMethodName.startswith("test_english") else "pl"
        self.load_patch = patch("musiccast_bridge.ui.Settings.load",
                                return_value=Settings(language=locale,
                                                      check_updates_at_startup=False))
        self.addCleanup(set_language, "pl")
        self.save_patch = patch("musiccast_bridge.ui.Settings.save")
        self.load_patch.start()
        self.addCleanup(self.load_patch.stop)
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)
        output_patch = patch("musiccast_bridge.windows_output.WindowsOutput.query",
                             return_value={"devices": [], "defaults": {}})
        output_patch.start()
        self.addCleanup(output_patch.stop)
        fit = MainWindow._fit_window
        # Geometry tests use a deliberate logical work area, independently of
        # the physical monitor resolution or the Linux offscreen screen size.
        with patch.object(
            MainWindow, "_fit_window", lambda window: fit(window, QRect(0, 0, 1280, 900))
        ):
            self.window = MainWindow()
        self.window.poll.stop()
        self.window.settings.host = ""

    def tearDown(self):
        self.window._quit()
        deadline = time.monotonic() + 8
        while self.window.worker.isRunning() and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        self.application.processEvents()
        self.assertFalse(self.window.worker.isRunning())

    def test_disconnected_controls_are_disabled(self):
        self.assertFalse(self.window.power.isEnabled())
        self.assertFalse(self.window.volume.isEnabled())

    def test_receiver_stop_button_exists(self):
        self.assertIn("stop", self.window.playback_buttons)

    def test_polish_legal_reader_and_standard_file_dialog_are_polish(self):
        self.window.settings_button.click()
        dialog = self.window._settings_window
        self.assertIn("tłumaczenie informacyjne", dialog.legal_text.toPlainText())
        dialog.documents.setCurrentIndex(dialog.documents.findData("TERMS.md"))
        self.assertTrue(dialog.legal_text.toPlainText().startswith("Zasady korzystania"))
        self.assertNotIn("Terms of use", dialog.legal_text.toPlainText())
        file = QFileDialog(self.window)
        file.setOption(QFileDialog.Option.DontUseNativeDialog)
        file.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.assertIn("Otwórz", file.labelText(QFileDialog.DialogLabel.Accept).replace("&", ""))
        file.deleteLater()

    def test_english_standard_file_dialog_is_english(self):
        file = QFileDialog(self.window)
        file.setOption(QFileDialog.Option.DontUseNativeDialog)
        file.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.assertIn("Open", file.labelText(QFileDialog.DialogLabel.Accept).replace("&", ""))
        file.deleteLater()

    def test_update_result_is_nonmodal_and_opens_only_the_release_on_click(self):
        self.window._result("updates", UpdateInfo(
            "available", "owner/musiccast", "0.3.0",
            "https://github.com/owner/musiccast/releases/tag/v0.3.0"))
        self.assertEqual(self.window.update_button.text(), "Nowa wersja!")
        self.window.update_button.click()
        dialog = self.window._settings_window
        self.assertIs(dialog.tabs.currentWidget(), dialog.updates_page)
        self.assertTrue(dialog.open_release.isEnabled())
        self.assertIn("0.3.0", dialog.update_status.text())
        self.assertFalse(self.window.worker.session.audio.active)
        with patch("musiccast_bridge.ui.QDesktopServices.openUrl") as open_url:
            dialog.open_release.click()
        self.assertEqual(open_url.call_args.args[0].toString(),
                         "https://github.com/owner/musiccast/releases/tag/v0.3.0")

    def test_update_preferences_are_saved_without_network_or_audio(self):
        self.window._show_updates()
        dialog = self.window._settings_window
        dialog.repository.setText("https://github.com/owner/musiccast.git")
        dialog.check_updates.setChecked(True)
        with patch("musiccast_bridge.ui.check_for_updates") as check:
            dialog._save()
        check.assert_not_called()
        self.assertEqual(self.window.settings.update_repository, "owner/musiccast")
        self.assertTrue(self.window.settings.check_updates_at_startup)

    def test_update_network_failure_preserves_receiver_notice(self):
        self.window._notice("Receiver message")
        self.window._failed("updates", "network failure")
        self.assertEqual(self.window.notice.toolTip(), "Receiver message")
        self.assertEqual(self.window.update_info.state, "unreachable")

    def test_english_main_window_and_settings_use_translated_controls(self):
        self.assertEqual(self.window.connect_button.text(), "Connect")
        self.assertEqual(self.window.audio_button.text(), "Listen from PC")
        self.assertEqual(self.window.settings_button.text(), "Settings…")
        self.window.settings_button.click()
        dialog = self.window._settings_window
        self.assertEqual(dialog.windowTitle(), "Settings")
        self.assertIn("MIT License", dialog.legal_text.toPlainText())
        self.assertFalse(dialog.isModal())
        self.assertIn("CABLE Input", self.window.routing_hint.toolTip())
        self.window.show()
        self.application.processEvents()
        self.assertEqual(self.window.minimumSize(), self.window.maximumSize())
        self.assertTrue(self.window.rect().contains(self.window.settings_button.geometry()))

    def test_settings_save_language_and_tray_without_starting_audio(self):
        self.window.settings_button.click()
        dialog = self.window._settings_window
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        dialog.tray_setting.setChecked(False)
        dialog._save()
        self.assertEqual(self.window.settings.language, "en")
        self.assertFalse(self.window.settings.close_to_tray)
        self.assertFalse(self.window.worker.session.audio.active)
        # The next launch changes language without rebuilding an active connection.
        self.assertEqual(self.window.connect_button.text(), "Połącz")
        self.assertFalse(dialog.isVisible())

    def test_diagnostics_is_read_only_and_updates_in_a_separate_window(self):
        self.window.diagnostics_button.click()
        dialog = self.window._diagnostics_window
        self.assertTrue(dialog.output.isReadOnly())
        self.assertFalse(dialog.isModal())
        self.assertFalse(dialog.copy_button.isEnabled())
        self.window.worker.session.audio.diagnostics.emit("test_event", code=200)
        dialog._refresh()
        self.assertIn("test_event", dialog.output.toPlainText())
        self.assertTrue(dialog.copy_button.isEnabled())
        dialog.close()

    def test_window_is_fixed_without_a_scrolling_container(self):
        self.window.show()
        self.application.processEvents()
        size = self.window.size()
        self.assertEqual(self.window.minimumSize(), self.window.maximumSize())
        self.assertEqual(self.window.findChildren(QScrollArea), [])
        self.window.resize(size.width() + 100, size.height() + 100)
        self.application.processEvents()
        self.assertEqual(self.window.size(), size)

    def test_discovery_selection_is_explicit_and_does_not_connect(self):
        self.window.host.setText("192.168.1.10")
        with patch.object(self.window.worker, "submit") as submit:
            self.window._result(
                "discover",
                [
                    DiscoveredReceiver("192.168.1.20", "Salon", "R-N602"),
                    DiscoveredReceiver("192.168.1.30", "Gabinet", "R-N602"),
                ],
            )
            self.window.found.setCurrentIndex(1)
            self.window.found.activated.emit(1)
            self.assertEqual(self.window.host.text(), "192.168.1.10")
            self.assertTrue(self.window.use_ip.isEnabled())
            self.window.use_ip.click()
            self.assertEqual(self.window.host.text(), "192.168.1.30")
            submit.assert_not_called()
        self.window._result("discover", [])
        self.assertFalse(self.window.use_ip.isEnabled())

    def test_saved_output_restores_by_name_and_missing_output_blocks_start(self):
        name = "CABLE Input (VB-Audio Virtual Cable) [Loopback]"
        self.window.settings.audio_device_name = name
        self.window._result("devices", [AudioDevice(21, name, 48000, 2)])
        self.assertEqual(self.window.audio_device.currentData(), 21)
        self.window._result("devices", [AudioDevice(4, name, 48000, 2)])
        self.assertEqual(self.window.audio_device.currentData(), 4)
        self.window._result("devices", [])
        self.assertTrue(self.window._device_missing)
        with patch.object(self.window.worker, "submit") as submit:
            self.window._start_audio()
            submit.assert_not_called()
        self.window.audio_device.setCurrentIndex(0)
        self.window._select_audio_device(0)
        self.assertFalse(self.window._device_missing)
        self.assertEqual(self.window.settings.audio_device_name, "")

    def test_installer_preference_selects_standard_cable_once(self):
        self.window.settings.prefer_virtual_cable = True
        name = "CABLE Input (VB-Audio Virtual Cable) [Loopback]"
        self.window._result("devices", [
            AudioDevice(12, "Hi-Fi CABLE Input (VB-Audio Hi-Fi Cable)", 48000, 2),
            AudioDevice(32, name, 48000, 2),
            AudioDevice(33, "CABLE In 16ch (VB-Audio Virtual Cable)", 48000, 16),
        ])
        self.assertEqual(self.window.audio_device.currentData(), 32)
        self.assertEqual(self.window.settings.audio_device_name, name)
        self.assertFalse(self.window.settings.prefer_virtual_cable)
        self.assertFalse(self.window._device_missing)

    def test_installer_preference_never_falls_back_to_speakers(self):
        self.window.settings.prefer_virtual_cable = True
        self.window._result("devices", [AudioDevice(4, "Speakers (Realtek)", 48000, 2)])
        self.assertTrue(self.window._device_missing)
        self.assertEqual(self.window.audio_device.currentData(), -1)
        with patch.object(self.window.worker, "submit") as submit:
            self.window._start_audio()
            submit.assert_not_called()

    def test_main_window_shows_live_rates_without_receiver_commands_or_resizing(self):
        snapshot = {
            "run": "test", "attempt": 1, "state": "playing", "sampled_at": 10,
            "audio_bytes": 0, "audio_packets": 0,
        }
        size = self.window.size()
        with patch.object(
            self.window.worker.session.audio.diagnostics, "snapshot", return_value=snapshot
        ), patch.object(self.window.worker, "submit") as submit:
            self.window._refresh_traffic(now=10)
            snapshot.update(sampled_at=12, audio_bytes=355000, audio_packets=250)
            self.window._refresh_traffic(now=12)
            self.assertIn("1,42 Mb/s", self.window.traffic_values["audio"].toolTip())
            self.assertIn("125,0 pak./s", self.window.traffic_values["audio"].toolTip())
            self.assertEqual(self.window.size(), size)
            submit.assert_not_called()

    def test_receiver_only_setup_selects_cable_without_starting_audio(self):
        name = "CABLE Input (VB-Audio Virtual Cable) [Loopback]"
        self.window._result("devices", [AudioDevice(21, name, 48000, 2)])
        with patch.object(self.window, "_devices"), patch.object(
            self.window.worker, "submit"
        ) as submit:
            self.window._show_routing()
            dialog = self.window._routing_window
            try:
                self.assertFalse(dialog.isModal())
                self.assertTrue(dialog.choose.isEnabled())
                dialog.choose.click()
                self.assertEqual(self.window.audio_device.currentData(), 21)
                self.assertEqual(self.window.settings.audio_device_name, name)
                self.assertFalse(self.window.audio_connecting)
                submit.assert_not_called()
            finally:
                dialog.close()

    def test_bounded_text_supports_non_bmp_characters(self):
        widget = BoundedLabel("Muzyka 🎵🎵 " * 20)
        widget.setFixedWidth(160)
        widget.show()
        self.application.processEvents()
        try:
            self.assertTrue(widget.toolTip().startswith("Muzyka 🎵🎵"))
            self.assertLessEqual(len(widget.text().splitlines()), 2)
            for line in widget.text().splitlines():
                self.assertLessEqual(
                    widget.fontMetrics().horizontalAdvance(line), widget.contentsRect().width()
                )
        finally:
            widget.close()

    def test_compact_layout_fits_the_work_area_or_reports_it_explicitly(self):
        self.window._fit_window(QRect(0, 0, 1024, 768))
        self.assertLessEqual(self.window.width(), 1000)
        self.assertLessEqual(self.window.height(), 736)
        with self.assertRaises(WindowLayoutError):
            self.window._fit_window(QRect(0, 0, 320, 240))

    def test_long_dynamic_content_does_not_move_controls_outside_window(self):
        import asyncio

        snapshot = asyncio.run(demo_receiver().connect())
        snapshot = replace(
            snapshot,
            model="Yamaha " * 30,
            input_names={"spotify": "Źródło " * 40},
            play_info={
                "track": "Bardzo długi tytuł " * 40,
                "artist": "Wykonawca " * 40,
                "attribute": 31,
            },
            status=replace(snapshot.status, mute=True),
        )
        self.window.show()
        self.application.processEvents()
        size = self.window.size()
        self.window._result("connect", snapshot)
        self.window._result(
            "discover",
            [
                DiscoveredReceiver(
                    "192.168.1.20",
                    "Długa nazwa urządzenia " * 40,
                    "R-N602",
                )
            ],
        )
        self.window.audio_device.addItem("Bardzo długa nazwa wyjścia " * 40, 1)
        self.window.audio_device.setCurrentIndex(1)
        self.window._notice("Nie można połączyć z amplitunerem. " * 30)
        self.application.processEvents()
        self.assertEqual(self.window.size(), size)
        self.assertIn("Nie można połączyć", self.window.notice.toolTip())
        for widget in self.window.content.findChildren(QWidget):
            if not widget.isVisible() or widget.parentWidget() is None:
                continue
            # Inspect actual controls, not the internal popup view of a native combo.
            if not isinstance(widget, QPushButton) and widget not in {
                self.window.host,
                self.window.found,
                self.window.source,
                self.window.volume,
                self.window.audio_device,
                self.window.notice,
                self.window.traffic_state,
                *self.window.traffic_values.values(),
            }:
                continue
            with self.subTest(
                control=widget.accessibleName() or widget.objectName() or type(widget).__name__
            ):
                self.assertTrue(widget.parentWidget().rect().contains(widget.geometry()))
                position = widget.mapTo(self.window.content, QPoint(0, 0))
                self.assertTrue(self.window.content.rect().contains(QRect(position, widget.size())))
                self.assertGreater(widget.width(), 0)
                self.assertGreater(widget.height(), 0)


if __name__ == "__main__":
    unittest.main()
