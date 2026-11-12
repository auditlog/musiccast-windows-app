import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from musiccast_bridge import __version__
from musiccast_bridge.versioning import version_tuple

ROOT = Path(__file__).resolve().parents[1]
tools = runpy.run_path(str(ROOT / "scripts/version_info.py"))


class VersionResourceTests(unittest.TestCase):
    def test_windows_resource_and_frozen_metadata_use_the_declared_version(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / "src/musiccast_bridge"
            source.mkdir(parents=True)
            (source / "versioning.py").write_bytes(
                (ROOT / "src/musiccast_bridge/versioning.py").read_bytes()
            )
            (source / "__init__.py").write_text(f'__version__ = "{__version__}"\n')
            (project / "pyproject.toml").write_text('[project]\ndynamic=["version"]\n')
            with patch.dict("os.environ", {"MUSICCAST_RELEASE_REPOSITORY": "owner/musiccast"}):
                resource, metadata = tools["prepare_version_info"](project)
            captured = {}

            def constructor(name):
                def capture(*args, **kwargs):
                    captured.setdefault(name, []).append((args, kwargs))
                    return {"name": name, "args": args, "kwargs": kwargs}

                return capture

            constructors = {
                name: constructor(name)
                for name in (
                    "VSVersionInfo",
                    "FixedFileInfo",
                    "StringFileInfo",
                    "StringTable",
                    "StringStruct",
                    "VarFileInfo",
                    "VarStruct",
                )
            }
            eval(
                compile(resource.read_text(), str(resource), "eval"),
                {"__builtins__": {}, **constructors},
            )
            fixed = captured["FixedFileInfo"][0][1]
            self.assertEqual(fixed["filevers"], (*version_tuple(__version__), 0))
            self.assertEqual(fixed["prodvers"], fixed["filevers"])
            values = dict(args for args, _ in captured["StringStruct"])
            self.assertEqual(values["FileVersion"], __version__)
            self.assertEqual(values["ProductVersion"], __version__)
            self.assertEqual(json.loads(metadata.read_text())["repository"], "owner/musiccast")

    def test_native_spec_supplies_and_verifies_version_resources(self):
        spec = (ROOT / "MusicCastBridge.spec").read_text()
        self.assertIn("version=str(version_file)", spec)
        self.assertIn('["verify_exe_version"]', spec)
