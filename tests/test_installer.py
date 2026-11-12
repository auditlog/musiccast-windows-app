import ctypes
import hashlib
import importlib.util
import io
import json
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from musiccast_bridge.installation import (
    APP_MUTEX,
    application_marker,
    is_standard_cable_name,
    prefer_installed_cable,
)
from musiccast_bridge.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "installer_tools", ROOT / "scripts" / "installer_tools.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
with patch.dict("sys.modules", {"installer_tools": installer}):
    BUILD_SPEC = importlib.util.spec_from_file_location(
        "build_installer", ROOT / "scripts" / "build_installer.py"
    )
    builder = importlib.util.module_from_spec(BUILD_SPEC)
    BUILD_SPEC.loader.exec_module(builder)


class InstallerPreferenceTests(unittest.TestCase):
    def test_frozen_first_run_uses_profile_but_preserves_existing_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "install.ini").write_text("[Audio]\nPreferCable=1\n", encoding="utf-8")
            settings = folder / "settings.json"
            fake_sys = SimpleNamespace(frozen=True, executable=str(folder / "MusicCastBridge.exe"))
            with patch("musiccast_bridge.installation.sys", fake_sys):
                self.assertTrue(prefer_installed_cable())
                self.assertTrue(Settings.load(settings).prefer_virtual_cable)
                Settings(audio_device_name="Speakers [Loopback]").save(settings)
                preserved = Settings.load(settings)
                self.assertEqual(preserved.audio_device_name, "Speakers [Loopback]")
                self.assertFalse(preserved.prefer_virtual_cable)

    def test_source_runs_do_not_inherit_an_installer_profile(self):
        with patch("musiccast_bridge.installation.sys", SimpleNamespace(frozen=False)):
            self.assertFalse(prefer_installed_cable())

    def test_standard_cable_excludes_hifi_extra_cables_and_16_channel_endpoint(self):
        self.assertTrue(is_standard_cable_name("CABLE Input (VB-Audio Virtual Cable) [Loopback]"))
        for name in (
            "Hi-Fi CABLE Input (VB-Audio Hi-Fi Cable)",
            "CABLE-A Input (VB-Audio Cable A)",
            "CABLE In 16ch (VB-Audio Virtual Cable)",
            "Speakers (Realtek)",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_standard_cable_name(name))

    def test_running_marker_is_held_and_closed_even_on_failure(self):
        api = SimpleNamespace(CreateMutexW=Mock(return_value=123), CloseHandle=Mock())
        with (
            patch("musiccast_bridge.installation.sys", SimpleNamespace(platform="win32")),
            patch.object(ctypes, "WinDLL", return_value=api, create=True),
        ):
            with self.assertRaisesRegex(ValueError, "desktop failed"):
                with application_marker():
                    api.CreateMutexW.assert_called_once_with(None, False, APP_MUTEX)
                    api.CloseHandle.assert_not_called()
                    raise ValueError("desktop failed")
        api.CloseHandle.assert_called_once_with(123)


class VendorPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.zip = self.folder / "cable.zip"
        self.files = {
            "Cable/VBCABLE_Setup_x64.exe": b"MZ synthetic fixture; never executed",
            "Cable/driver.inf": b"synthetic inf",
            "Cable/driver.cat": b"synthetic catalog",
            "Cable/drivers/cable.sys": b"synthetic driver",
            "Cable/readme.txt": b"vendor notice",
        }

    def write_zip(self, files=None):
        with zipfile.ZipFile(self.zip, "w") as archive:
            for name, content in (self.files if files is None else files).items():
                archive.writestr(name, content)

    def test_preserves_every_original_file_and_records_checksum(self):
        self.write_zip()
        target = self.folder / "staged"
        root, manifest = installer.stage_cable(self.zip, target)
        self.assertEqual(root, target / "Cable")
        self.assertEqual(
            manifest["archive_sha256"], hashlib.sha256(self.zip.read_bytes()).hexdigest()
        )
        for name, content in self.files.items():
            self.assertEqual((target / name).read_bytes(), content)
            self.assertEqual(manifest["files"][name], hashlib.sha256(content).hexdigest())

    def test_vendor_files_at_archive_root_are_supported(self):
        self.write_zip({name.removeprefix("Cable/"): data for name, data in self.files.items()})
        target = self.folder / "staged"
        root, manifest = installer.stage_cable(self.zip, target)
        self.assertEqual(root, target)
        self.assertEqual(len(manifest["files"]), len(self.files))

    def test_rejects_windows_traversal_and_ambiguous_paths_before_replacing_stage(self):
        target = self.folder / "staged"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("previous build", encoding="utf-8")
        for bad in (
            "../escape",
            "C:/escape",
            "\\\\server\\share",
            "Cable/file:stream",
            "Cable/CON.txt",
        ):
            with self.subTest(path=bad):
                self.write_zip({**self.files, bad: b"bad"})
                with self.assertRaises(installer.PackageError):
                    installer.stage_cable(self.zip, target)
                self.assertTrue(marker.exists())
        self.assertFalse((self.folder / "escape").exists())

    def test_rejects_symlinks_case_collisions_and_incomplete_payloads(self):
        self.write_zip()
        with zipfile.ZipFile(self.zip, "a") as archive:
            entry = zipfile.ZipInfo("Cable/link")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, "../../outside")
        with self.assertRaises(installer.PackageError):
            installer.stage_cable(self.zip, self.folder / "out")
        for files in (
            {**self.files, "cable/DRIVER.INF": b"collision"},
            {name: data for name, data in self.files.items() if not name.endswith(".cat")},
        ):
            self.write_zip(files)
            with self.assertRaises(installer.PackageError):
                installer.stage_cable(self.zip, self.folder / "out")

    def test_rejects_excessive_expanded_size(self):
        self.write_zip()
        with patch.object(installer, "MAX_EXPANDED", 10):
            with self.assertRaises(installer.PackageError):
                installer.stage_cable(self.zip, self.folder / "out")

    def test_preparation_bundles_attribution_and_generates_versioned_paths(self):
        self.write_zip()
        (self.folder / "pyproject.toml").write_text(
            '[project]\nversion="1.2.3"\n', encoding="utf-8"
        )
        app = self.folder / "dist" / "MusicCastBridge"
        app.mkdir(parents=True)
        (app / "MusicCastBridge.exe").write_bytes(b"MZ synthetic app")
        notice = self.folder / "installer" / "VB-CABLE-NOTICE.txt"
        notice.parent.mkdir()
        notice.write_text("VB-Audio donationware", encoding="utf-8")
        shutil.copytree(ROOT / "src/musiccast_bridge/legal_texts",
                        self.folder / "src/musiccast_bridge/legal_texts")
        with patch.object(
            installer, "CABLE_SHA256", hashlib.sha256(self.zip.read_bytes()).hexdigest()
        ):
            self.assertEqual(installer.prepare_installer(self.folder, self.zip), "1.2.3")
        stage = self.folder / "build" / "installer"
        generated = (stage / "generated.iss").read_text(encoding="utf-8-sig")
        self.assertIn('#define BridgeVersion "1.2.3"', generated)
        self.assertIn(str(app), generated)
        self.assertEqual(
            (stage / "VB-CABLE-NOTICE.txt").read_text(encoding="utf-8-sig"), "VB-Audio donationware"
        )
        manifest = json.loads((stage / "vbcable-package.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["app_version"], "1.2.3")
        self.assertTrue((stage / "license-pl.txt").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("tłumaczenie informacyjne",
                      (stage / "license-pl.txt").read_text(encoding="utf-8-sig"))
        self.assertIn("Permission is hereby granted",
                      (stage / "license-en.txt").read_text(encoding="utf-8-sig"))
        self.assertIn("Prywatność", (stage / "info-pl.txt").read_text(encoding="utf-8-sig"))
        self.assertNotIn("## English", (stage / "info-pl.txt").read_text(encoding="utf-8-sig"))
        self.assertIn("Privacy", (stage / "info-en.txt").read_text(encoding="utf-8-sig"))
        self.assertNotIn("Prywatność", (stage / "info-en.txt").read_text(encoding="utf-8-sig"))

    def test_wizard_prompts_for_language_and_uses_selected_language_documents(self):
        script = (ROOT / "installer/MusicCastBridge.iss").read_text(encoding="utf-8-sig")
        self.assertIn("ShowLanguageDialog=yes", script)
        for language, code in (("polish", "pl"), ("english", "en")):
            row = next(
                line for line in script.splitlines() if line.startswith(f'Name: "{language}";')
            )
            self.assertIn(f'license-{code}.txt', row)
            self.assertIn(f'info-{code}.txt', row)
        self.assertIn('Key: "LanguageSelection"', script)
        self.assertIn("GetTickCount@kernel32.dll", script)

    def test_release_hash_mismatch_stops_before_staging(self):
        self.write_zip()
        with self.assertRaisesRegex(installer.PackageError, "SHA-256"):
            installer.prepare_installer(self.folder, self.zip)
        self.assertFalse((self.folder / "build").exists())

    def test_download_is_bounded_and_rejects_untrusted_redirects(self):
        for url, content, limit in (
            ("http://download.vb-audio.com/cable.zip", b"zip", 100),
            ("https://other.example/cable.zip", b"zip", 100),
            (installer.CABLE_URL, b"oversized", 2),
        ):
            with self.subTest(url=url, limit=limit):
                response = io.BytesIO(content)
                response.url = url
                with (
                    patch.object(installer.urllib.request, "urlopen", return_value=response),
                    patch.object(installer, "MAX_DOWNLOAD", limit),
                ):
                    with self.assertRaises(installer.PackageError):
                        installer.download_cable(self.zip)
                self.assertFalse(self.zip.exists())

    def test_license_collection_copies_notices_and_excludes_other_metadata(self):
        metadata = self.folder / "test.dist-info"
        metadata.mkdir()
        (metadata / "LICENSE.txt").write_text("license text", encoding="utf-8")
        (metadata / "direct_url.json").write_text("private-build-path", encoding="utf-8")
        distribution = SimpleNamespace(
            metadata={"Name": "test-package"},
            files=[Path("test.dist-info/LICENSE.txt"), Path("test.dist-info/direct_url.json")],
            locate_file=lambda entry: self.folder / entry,
        )
        with patch.object(
            installer.importlib.metadata, "distributions", return_value=[distribution]
        ):
            installer.collect_licenses(self.folder / "app")
        target = self.folder / "app" / "third-party-licenses"
        self.assertEqual(
            (target / "test-package/test.dist-info/LICENSE.txt").read_text(), "license text"
        )
        self.assertFalse((target / "test-package/test.dist-info/direct_url.json").exists())
        self.assertIn("MIT License", (self.folder / "app/LICENSE").read_text())
        self.assertTrue((target / "LGPL-3.0.txt").is_file())
        self.assertTrue((target / "GPL-3.0.txt").is_file())
        inventory = json.loads((target / "DEPENDENCIES.json").read_text())
        self.assertEqual(inventory[0]["name"], "test-package")


class BuildPipelineTests(unittest.TestCase):
    def test_build_tests_and_freeze_precede_installer_compilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            archive = project / "cable.zip"
            archive.write_bytes(b"synthetic vendor archive")
            artifact = project / "dist/installer/MusicCastBridge-1.2.3-Setup-x64.exe"
            commands = []

            def run(command):
                commands.append(command)
                if command[0] == "ISCC.exe":
                    artifact.parent.mkdir(parents=True)
                    artifact.write_bytes(b"MZ synthetic setup")

            fake_sys = SimpleNamespace(
                platform="win32", executable="python.exe", stderr=io.StringIO()
            )
            with (
                patch.multiple(
                    builder,
                    ROOT=project,
                    sys=fake_sys,
                    platform=SimpleNamespace(machine=lambda: "AMD64"),
                    find_compiler=Mock(return_value="ISCC.exe"),
                    run=Mock(side_effect=run),
                    collect_licenses=Mock(),
                    prepare_installer=Mock(return_value="1.2.3"),
                ),
                patch("builtins.print"),
            ):
                self.assertEqual(builder.main(["--vbcable-zip", str(archive)]), 0)
            self.assertEqual([command[2] for command in commands[:2]], ["pip", "unittest"])
            self.assertIn("test-detection.ps1", commands[2][-1])
            self.assertEqual(commands[3][2], "PyInstaller")
            self.assertEqual(commands[-1][0], "ISCC.exe")
            self.assertTrue(artifact.exists())

    def test_non_windows_refuses_to_run_compiler_or_install_dependencies(self):
        with (
            patch.object(builder, "sys", SimpleNamespace(platform="linux", stderr=io.StringIO())),
            patch.object(builder, "run") as run,
            patch("builtins.print"),
        ):
            self.assertEqual(builder.main([]), 1)
            run.assert_not_called()
