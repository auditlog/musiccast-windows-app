import ast
import runpy
import string
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from musiccast_bridge import i18n, legal
from musiccast_bridge.audio import user_audio_error
from musiccast_bridge.models import input_label
from musiccast_bridge.settings import Settings
from musiccast_bridge.telemetry import TrafficView, traffic_text


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("pl")

    def test_language_and_output_preferences_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(language="en", close_to_tray=False, auto_output=True,
                                windows_output_id="{endpoint}", windows_output_name="CABLE Input")
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            path.write_text('{"language":"invalid","auto_output":"false","windows_output_id":8}')
            restored = Settings.load(path)
            self.assertEqual(restored.language, "pl")
            self.assertFalse(restored.auto_output)
            self.assertEqual(restored.windows_output_id, "")

    def test_installer_language_only_applies_to_first_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "install.ini").write_text("[General]\nLanguage=english\n")
            profile = SimpleNamespace(frozen=True, executable=str(folder / "MusicCastBridge.exe"))
            with patch("musiccast_bridge.installation.sys", profile):
                path = folder / "settings.json"
                self.assertEqual(Settings.load(path).language, "en")
                Settings(language="pl").save(path)
                self.assertEqual(Settings.load(path).language, "pl")

    def test_new_installer_selection_applies_once_and_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            profile = SimpleNamespace(frozen=True, executable=str(folder / "MusicCastBridge.exe"))
            path = folder / "settings.json"
            Settings(host="receiver.local", language="pl", close_to_tray=False,
                     audio_device_name="CABLE Input", auto_output=True).save(path)
            with patch("musiccast_bridge.installation.sys", profile):
                (folder / "install.ini").write_text(
                    "[General]\nLanguage=english\nLanguageSelection=installation-1\n")
                settings = Settings.load(path)
                self.assertEqual(settings.language, "en")
                self.assertEqual(settings.host, "receiver.local")
                self.assertFalse(settings.close_to_tray)
                self.assertTrue(settings.auto_output)
                self.assertEqual(settings.audio_device_name, "CABLE Input")
                settings.language = "pl"
                settings.save(path)
                self.assertEqual(Settings.load(path).language, "pl")
                (folder / "install.ini").write_text(
                    "[General]\nLanguage=english\nLanguageSelection=installation-2\n")
                self.assertEqual(Settings.load(path).language, "en")

    def test_localized_documents_match_the_reference_sections_and_preserve_original_mit(self):
        root = Path(__file__).resolve().parents[1]
        generator = runpy.run_path(str(root / "scripts/localize_documents.py"))
        for name, expected in generator["expected_documents"](root).items():
            actual = (root / "src/musiccast_bridge/legal_texts" / name).read_text(encoding="utf-8")
            self.assertEqual(actual, expected, f"Regenerate documents: {name}")
        self.assertEqual(legal.document("LICENSE", "en"), (root / "LICENSE").read_text())
        for locale, title, excluded in (("pl", "Zasady korzystania", "Terms of use"),
                                         ("en", "Terms of use", "Zasady korzystania")):
            text = legal.document("TERMS.md", locale)
            self.assertTrue(text.startswith(title))
            self.assertNotIn(excluded, text)
            self.assertNotIn("## English", text)
            self.assertNotIn("## Polski", text)
        with self.assertRaises(ValueError):
            legal.document("TERMS.md", "../../en")

    def test_external_audio_errors_have_localized_user_messages(self):
        for locale, expected in (("pl", "Nie udało się"), ("en", "Audio streaming failed")):
            i18n.set_language(locale)
            message = user_audio_error(RuntimeError("No response to RECORD"))
            self.assertIn(expected, message)
            self.assertNotIn("No response", message)

    def test_app_owned_visible_literal_labels_are_translated(self):
        neutral = {"", "—", "MusicCast Bridge", "Polski", "English"}
        visible = {"label", "button", "QCheckBox", "QPushButton", "QLabel", "BoundedLabel",
                   "setText", "setWindowTitle", "setToolTip", "setAccessibleName",
                   "setPlaceholderText", "setOkButtonText", "setCancelButtonText",
                   "addAction", "addItem", "addTab"}
        for name in ("ui.py", "app.py", "cli.py"):
            path = Path(i18n.__file__).with_name(name)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                function = (node.func.attr if isinstance(node.func, ast.Attribute)
                            else node.func.id if isinstance(node.func, ast.Name) else "")
                index = 1 if function == "addTab" else 0
                if function in visible and len(node.args) > index:
                    text = node.args[index]
                    if isinstance(text, ast.Constant) and isinstance(text.value, str):
                        self.assertIn(
                            text.value, neutral, f"Untranslated label {name}:{node.lineno}"
                        )
                for option in node.keywords:
                    if option.arg in {"description", "help"} and isinstance(
                        option.value, ast.Constant
                    ):
                        if isinstance(option.value.value, str):
                            self.fail(f"Untranslated help {name}:{node.lineno}")

    def test_both_languages_preserve_format_fields_and_unknown_receiver_metadata(self):
        fields = string.Formatter()
        for source, english in i18n._english.items():
            original = {field for _, field, _, _ in fields.parse(source) if field is not None}
            translated = {field for _, field, _, _ in fields.parse(english) if field is not None}
            self.assertEqual(original, translated, source)
            self.assertTrue(english, source)
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Połącz"), "Connect")
        self.assertEqual(input_label("net_radio"), "Internet radio")
        self.assertEqual(i18n.tr("Żółte urządzenie — user name"), "Żółte urządzenie — user name")
        self.assertIn("1.42", traffic_text(TrafficView("Streaming", audio_mbps=1.42))["audio"])
        i18n.set_language("pl")
        self.assertIn("1,42", traffic_text(TrafficView("Streaming", audio_mbps=1.42))["audio"])

    def test_all_explicit_translation_keys_exist_in_the_catalog(self):
        for path in Path(i18n.__file__).parent.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "tr" and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    self.assertIn(node.args[0].value, i18n._english, str(path))

    def test_legal_documents_are_shipped_and_do_not_relicense_dependencies(self):
        self.assertIn("tłumaczenie informacyjne", legal.document("LICENSE"))
        self.assertIn("Zasady korzystania", legal.document("TERMS.md"))
        self.assertNotIn("## English", legal.document("TERMS.md"))
        self.assertIn("Prywatność", legal.document("PRIVACY.md"))
        self.assertIn("LGPL", legal.document("THIRD_PARTY_NOTICES.md"))
        self.assertIn("MIT License", legal.document("LICENSE_ORIGINAL"))
        with self.assertRaises(ValueError):
            legal.document("../../settings.json")
