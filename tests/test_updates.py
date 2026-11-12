import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from musiccast_bridge import __version__
from musiccast_bridge.updates import check_for_updates, release_info
from musiccast_bridge.versioning import github_repository, origin_repository, project_version


class UpdateTests(unittest.TestCase):
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
        with patch("musiccast_bridge.updates.urllib.request.build_opener", return_value=opener):
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

    def test_unconfigured_origin_does_not_make_network_requests(self):
        with (
            patch("musiccast_bridge.updates.bundled_repository", return_value=""),
            patch("musiccast_bridge.updates.origin_repository", return_value=""),
            patch("musiccast_bridge.updates.urllib.request.build_opener") as build,
        ):
            self.assertEqual(check_for_updates().state, "unconfigured")
            build.assert_not_called()

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
