import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from musiccast_bridge import __version__
from musiccast_bridge.updates import (
    UpdateError,
    _AssetRedirect,
    check_for_updates,
    download_update,
    launch_update,
    release_info,
)
from musiccast_bridge.versioning import (
    DEFAULT_UPDATE_REPOSITORY,
    default_update_repository,
    github_repository,
    origin_repository,
    project_version,
)


class UpdateTests(unittest.TestCase):
    def installer_info(self, content=b"MZ synthetic installer"):
        return release_info({
            "tag_name": "v0.3.0",
            "assets": [{"name": "MusicCastBridge-0.3.0-Setup-x64.exe",
                        "size": len(content),
                        "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
                        "browser_download_url": "https://evil.example/payload.exe"}],
        }, "owner/repo", "0.2.2")

    def test_installer_requires_exact_asset_name_size_digest_and_stable_release(self):
        info = self.installer_info()
        self.assertEqual(info.installer_url,
                         "https://github.com/owner/repo/releases/download/v0.3.0/"
                         "MusicCastBridge-0.3.0-Setup-x64.exe")
        for changes in (
            {"digest": None}, {"digest": "sha256:invalid"}, {"size": True},
            {"size": 0}, {"size": 536870913},
            {"name": "other.exe"}, {"name": "../MusicCastBridge-0.3.0-Setup-x64.exe"},
        ):
            asset = {"name": "MusicCastBridge-0.3.0-Setup-x64.exe",
                     "size": 100, "digest": "sha256:" + "a" * 64} | changes
            result = release_info({"tag_name": "v0.3.0", "assets": [asset]},
                                  "owner/repo", "0.2.2")
            self.assertEqual(result.state, "available")
            self.assertFalse(result.installer_url)

    def test_download_verifies_bytes_reports_progress_and_never_starts_a_process(self):
        content = b"MZ" + bytes(200000)
        info = self.installer_info(content)
        response = io.BytesIO(content)
        response.geturl = lambda: "https://release-assets.githubusercontent.com/asset?signature=test"
        progress = []
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("musiccast_bridge.updates.config_directory", return_value=Path(temp)),
            patch("musiccast_bridge.updates.urllib.request.build_opener",
                  return_value=Mock(open=Mock(return_value=response))),
            patch("musiccast_bridge.updates.subprocess.Popen") as process,
        ):
            target = download_update(info, lambda *values: progress.append(values))
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(target.name, "MusicCastBridge-0.3.0-Setup-x64.exe")
            self.assertEqual(progress[-1], (len(content), len(content)))
            self.assertEqual(list(target.parent.iterdir()), [target])
            process.assert_not_called()

    def test_corrupt_truncated_oversized_or_non_exe_download_is_removed(self):
        from dataclasses import replace

        for body, info in (
            (b"MZ corrupt content", self.installer_info()),
            (b"MZ", self.installer_info()),
            (b"MZ" + bytes(200), self.installer_info()),
            (b"not an EXE", self.installer_info(b"not an EXE")),
            (b"MZ synthetic installer", replace(self.installer_info(), installer_sha256="0" * 64)),
        ):
            with self.subTest(body=body[:30]), tempfile.TemporaryDirectory() as temp:
                response = io.BytesIO(body)
                response.geturl = lambda: "https://github.com/asset"
                with (
                    patch("musiccast_bridge.updates.config_directory", return_value=Path(temp)),
                    patch("musiccast_bridge.updates.urllib.request.build_opener",
                          return_value=Mock(open=Mock(return_value=response))),
                    self.assertRaises(UpdateError),
                ):
                    download_update(info)
                self.assertEqual(list((Path(temp) / "updates").iterdir()), [])

    def test_cancellation_removes_partial_download(self):
        cancelled = threading.Event()
        cancelled.set()
        response = io.BytesIO(b"MZ synthetic installer")
        response.geturl = lambda: "https://github.com/asset"
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("musiccast_bridge.updates.config_directory", return_value=Path(temp)),
            patch("musiccast_bridge.updates.urllib.request.build_opener",
                  return_value=Mock(open=Mock(return_value=response))),
            self.assertRaisesRegex(UpdateError, "anulowano"),
        ):
            download_update(self.installer_info(), cancelled=cancelled)
            self.assertEqual(list((Path(temp) / "updates").iterdir()), [])

    def test_asset_redirects_cannot_downgrade_or_leave_github(self):
        handler = _AssetRedirect()
        for target in ("http://github.com/file", "https://github.com.evil.test/file",
                       "https://user:password@github.com/file", "https://github.com:444/file",
                       "file:///tmp/update.exe"):
            with self.assertRaises(UpdateError):
                handler.redirect_request(None, None, 302, "Found", {}, target)

    def test_network_failure_removes_the_staging_directory(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("musiccast_bridge.updates.config_directory", return_value=Path(temp)),
            patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=Mock(
                open=Mock(side_effect=urllib.error.URLError("connection interrupted")),
            )),
        ):
            with self.assertRaisesRegex(UpdateError, "pobrać"):
                download_update(self.installer_info())
            self.assertEqual(list((Path(temp) / "updates").iterdir()), [])

    def test_installer_launch_rechecks_digest_and_waits_for_helper_acknowledgement(self):
        from types import SimpleNamespace

        content = b"MZ synthetic installer"
        info = self.installer_info(content)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "MusicCastBridge-0.3.0-Setup-x64.exe"
            path.write_bytes(content)
            process = Mock(poll=Mock(return_value=None))
            commands = []

            def spawn(command, **kwargs):
                commands.append(command)
                ready = Path(command[command.index("-ReadyFile") + 1])
                ready.write_text("ready")
                return process

            profile = SimpleNamespace(platform="win32", frozen=True,
                                      executable=str(Path(temp) / "MusicCastBridge.exe"))
            with (
                patch("musiccast_bridge.updates.sys", profile),
                patch("musiccast_bridge.updates.subprocess.Popen", side_effect=spawn) as popen,
            ):
                launch_update(path, info)
                self.assertIn("-File", commands[0])
                self.assertIn(str(path), commands[0])
                self.assertIn(str(path.parent), commands[0])
                self.assertNotIn("-Command", commands[0])
                path.write_bytes(b"MZ changed")
                with self.assertRaisesRegex(UpdateError, "zmienił się"):
                    launch_update(path, info)
                self.assertEqual(popen.call_count, 1)

    def test_version_comparison_is_numeric_and_ignores_drafts_and_prereleases(self):
        newer = release_info({"tag_name": "v0.10.0"}, "owner/musiccast", "0.9.0")
        self.assertEqual(newer.state, "available")
        self.assertEqual(newer.version, "0.10.0")
        self.assertEqual(
            newer.release_url, "https://github.com/owner/musiccast/releases/tag/v0.10.0"
        )
        for tag in ("v0.2.0", "v0.1.9"):
            self.assertEqual(
                release_info({"tag_name": tag}, "owner/repo", "0.2.0").state, "current"
            )
        for flag in ("draft", "prerelease"):
            self.assertEqual(
                release_info({"tag_name": "v3.0.0", flag: True}, "owner/repo", "0.2.0").state,
                "no_release",
            )

    def test_release_data_cannot_supply_an_external_link_or_untrusted_tag(self):
        result = release_info(
            {"tag_name": "v2.0.0", "html_url": "https://evil.example/a.exe"}, "owner/repo", "0.2.0"
        )
        self.assertTrue(result.release_url.startswith("https://github.com/owner/repo/"))
        for tag in (None, "../../evil", "v1.0.0-rc1", "v01.2.3", "999999.0.0"):
            self.assertEqual(
                release_info({"tag_name": tag}, "owner/repo", "0.2.0").state, "invalid_response"
            )

    def test_repository_accepts_origin_and_rejects_tokens_other_hosts_and_paths(self):
        for value in (
            "owner/repo",
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "git@github.com:owner/repo.git",
            "ssh://git@github.com/owner/repo.git",
            "ssh://git@ssh.github.com:443/owner/repo.git",
        ):
            self.assertEqual(github_repository(value), "owner/repo")
        for value in (
            "https://github.com.evil.test/owner/repo",
            "https://token@github.com/o/r",
            "https://github.com/o/r/releases",
            "https://github.com/o/r?token=secret",
            "../repo",
            "owner/..",
            "file:///etc/passwd",
            "",
        ):
            with self.assertRaises(ValueError):
                github_repository(value)

    def test_check_is_bounded_read_only_and_sends_no_credentials(self):
        response = io.BytesIO(json.dumps({"tag_name": "v0.3.0"}).encode())
        opener = Mock(open=Mock(return_value=response))
        with (
            patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener),
            patch("musiccast_bridge.updates.default_update_repository",
                  side_effect=AssertionError("Explicit repository must override the default")),
        ):
            result = check_for_updates("owner/repo", "0.2.0")
        self.assertEqual(result.state, "available")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url, "https://api.github.com/repos/owner/repo/releases/latest"
        )
        self.assertIsNone(request.data)
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 6)

    def test_offline_rate_limit_private_repo_and_oversized_response_are_statuses(self):
        for code, expected in (
            (404, "no_release"),
            (403, "rate_limited"),
            (429, "rate_limited"),
            (500, "unreachable"),
        ):
            opener = Mock(
                open=Mock(
                    side_effect=urllib.error.HTTPError(
                        "https://api.github.com", code, "error", {}, None
                    )
                )
            )
            with patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener):
                self.assertEqual(check_for_updates("owner/repo").state, expected)
        opener.open.side_effect = urllib.error.URLError("offline")
        with patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener):
            self.assertEqual(check_for_updates("owner/repo").state, "unreachable")
        opener.open.side_effect = None
        opener.open.return_value = io.BytesIO(b"x" * 1_048_577)
        with patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener):
            self.assertEqual(check_for_updates("owner/repo").state, "invalid_response")

    def test_empty_setting_uses_official_or_bundled_repository_without_git(self):
        for bundled, expected in (("", DEFAULT_UPDATE_REPOSITORY), ("owner/fork", "owner/fork")):
            response = io.BytesIO(json.dumps({"tag_name": "v0.3.0"}).encode())
            opener = Mock(open=Mock(return_value=response))
            with (
                patch("musiccast_bridge.versioning.bundled_repository", return_value=bundled),
                patch("musiccast_bridge.versioning.subprocess.run",
                      side_effect=AssertionError("Runtime update check must not spawn Git")),
                patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener),
            ):
                result = check_for_updates("", "0.2.0")
            self.assertEqual(result.state, "available")
            self.assertEqual(result.repository, expected)
            self.assertEqual(opener.open.call_args.args[0].full_url,
                             f"https://api.github.com/repos/{expected}/releases/latest")

    def test_default_is_available_from_source_and_invalid_or_missing_frozen_metadata(self):
        with (
            patch("musiccast_bridge.versioning.sys.frozen", False, create=True),
            patch("musiccast_bridge.versioning.subprocess.run",
                  side_effect=AssertionError("Settings must not spawn Git")),
        ):
            self.assertEqual(default_update_repository(), DEFAULT_UPDATE_REPOSITORY)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            metadata = folder / "build-info.json"
            with (
                patch("musiccast_bridge.versioning.sys.frozen", True, create=True),
                patch("musiccast_bridge.versioning.__file__", str(folder / "versioning.py")),
            ):
                self.assertEqual(default_update_repository(), DEFAULT_UPDATE_REPOSITORY)
                for value, expected in (
                    ("https://github.com/owner/fork", "owner/fork"),
                    ("", DEFAULT_UPDATE_REPOSITORY),
                    (None, DEFAULT_UPDATE_REPOSITORY),
                    ("https://evil.example/owner/repo", DEFAULT_UPDATE_REPOSITORY),
                ):
                    metadata.write_text(json.dumps({"repository": value}))
                    self.assertEqual(default_update_repository(), expected)
                metadata.write_text("invalid JSON")
                self.assertEqual(default_update_repository(), DEFAULT_UPDATE_REPOSITORY)

    def test_git_origin_can_be_read_without_git_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / ".git").mkdir()
            (folder / ".git/config").write_text(
                '[remote "origin"]\nurl = git@github.com:owner/musiccast.git\n'
            )
            with patch("musiccast_bridge.versioning.subprocess.run", side_effect=FileNotFoundError):
                self.assertEqual(origin_repository(folder), "owner/musiccast")

    def test_project_has_one_declared_version(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(project_version(root), __version__)

    def test_update_settings_survive_restart(self):
        from musiccast_bridge.settings import Settings

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            Settings(check_updates_at_startup=False, update_repository="owner/musiccast").save(path)
            saved = Settings.load(path)
            self.assertFalse(saved.check_updates_at_startup)
            self.assertEqual(saved.update_repository, "owner/musiccast")


@unittest.skipUnless(sys.platform == "win32", "Native Windows installer handoff")
class NativeInstallerHandoffTests(unittest.TestCase):
    def test_helper_waits_for_parent_exit_before_launching_with_app_only_arguments(self):
        from musiccast_bridge import updates

        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
            "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        with tempfile.TemporaryDirectory(prefix="bridge update test ") as temp:
            folder = Path(temp)
            marker, ready = folder / "launched.txt", folder / "ready"
            # Exercise the real handoff without installing anything or changing audio.
            installer = folder / "fake installer.cmd"
            installer.write_text('@echo off\n> "%~dp0launched.txt" echo %*\n', encoding="ascii")
            parent = subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.stdin.read()"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
            helper = None
            try:
                helper = subprocess.Popen([
                    str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(Path(updates.__file__).with_name("update_installer.ps1")),
                    "-Installer", str(installer), "-ParentProcessId", str(parent.pid),
                    "-InstallDirectory", str(folder), "-Language", "polish",
                    "-ReadyFile", str(ready),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
                deadline = time.monotonic() + 15
                while not ready.exists() and helper.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(ready.exists(), "Helper did not acknowledge startup")
                self.assertFalse(
                    marker.exists(), "Installer launched while parent was still running"
                )
                parent.stdin.close()
                parent.wait(timeout=5)
                output, error = helper.communicate(timeout=15)
                self.assertEqual(helper.returncode, 0, (output, error))
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                arguments = marker.read_text()
                self.assertIn("/COMPONENTS=app", arguments)
                self.assertIn("/NORESTART", arguments)
                self.assertIn(folder.name, arguments)
                self.assertFalse(ready.exists())
            finally:
                for process in (parent, helper):
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
