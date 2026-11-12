"""Version and repository parsing shared by the app and its build scripts.

No application imports: the PyInstaller spec can load this file with runpy.
"""

import ast
import configparser
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


def version_tuple(value, tag=False):
    if not isinstance(value, str):
        raise ValueError("Invalid version")
    if tag and value.startswith("v"):
        value = value[1:]
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("Version must be X.Y.Z")
    numbers = tuple(int(part) for part in value.split("."))
    if any(part > 65535 for part in numbers):
        raise ValueError("Windows version component exceeds 65535")
    return numbers


def project_version(project):
    project = Path(project)
    data = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    # Static versions remain supported for third-party build fixtures.
    version = data.get("version")
    if version is None:
        tree = ast.parse((project / "src/musiccast_bridge/__init__.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
            ):
                version = ast.literal_eval(node.value)
                break
    version_tuple(version)
    return version


def github_repository(value):
    """Normalize a GitHub slug or Git origin without accepting credentials/other hosts."""
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise ValueError("Invalid GitHub repository")
    value = value.strip()
    if value.startswith("git@github.com:"):
        value = value[len("git@github.com:") :]
    elif "://" in value:
        parsed = urlsplit(value)
        https = parsed.scheme == "https" and parsed.netloc.casefold() == "github.com"
        ssh = parsed.scheme == "ssh" and parsed.netloc.casefold() in {
            "git@github.com",
            "git@github.com:22",
            "git@ssh.github.com:443",
        }
        if not (https or ssh) or parsed.query or parsed.fragment:
            raise ValueError("Use https://github.com/owner/repo")
        value = parsed.path.strip("/")
    else:
        value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", value):
        raise ValueError("Use owner/repo")
    if value.split("/")[1] in {".", ".."}:
        raise ValueError("Invalid repository name")
    return value


def origin_repository(project):
    """Read local Git configuration; no authentication, network, or credential helpers."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
            check=False,
            **({"creationflags": 0x08000000} if sys.platform == "win32" else {}),
        )
        if result.returncode == 0:
            return github_repository(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # Windows users may have Git only in WSL. Reading an ordinary Git config
    # also works without a git.exe on their Windows PATH.
    try:
        location = Path(project) / ".git"
        if location.is_file():
            marker = location.read_text(encoding="utf-8").strip()
            if not marker.startswith("gitdir: "):
                return ""
            location = (Path(project) / marker[len("gitdir: ") :]).resolve()
        config = configparser.ConfigParser(interpolation=None)
        config.read(location / "config", encoding="utf-8")
        return github_repository(config.get('remote "origin"', "url"))
    except (OSError, ValueError, configparser.Error):
        return ""


def bundled_repository():
    if not getattr(sys, "frozen", False):
        return ""
    try:
        data = json.loads(Path(__file__).with_name("build-info.json").read_text(encoding="utf-8"))
        return github_repository(data["repository"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""
