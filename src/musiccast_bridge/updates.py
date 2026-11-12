"""GitHub release checks and user-initiated, verified Windows installer updates."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from . import __version__
from .i18n import language, tr
from .settings import config_directory
from .versioning import default_update_repository, github_repository, version_tuple

_LIMIT = 1_048_576
_INSTALLER_LIMIT = 512 * 1024 * 1024
_DOWNLOAD_HOSTS = {
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
}


@dataclass(frozen=True)
class UpdateInfo:
    state: str = "idle"
    repository: str = ""
    version: str = ""
    release_url: str = ""
    installer_url: str = ""
    installer_sha256: str = ""
    installer_size: int = 0


class UpdateError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def check_for_updates(repository="", current=__version__):
    """Run in the worker thread; a failure never blocks receiver commands."""
    try:
        repository = (
            github_repository(repository)
            if repository.strip()
            else default_update_repository()
        )
    except ValueError:
        return UpdateInfo("invalid_repository")
    if not repository:
        return UpdateInfo("unconfigured")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": f"MusicCastBridge/{current}",
        },
    )
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=6) as response:
            body = response.read(_LIMIT + 1)
        if len(body) > _LIMIT:
            return UpdateInfo("invalid_response", repository)
        return release_info(json.loads(body), repository, current)
    except urllib.error.HTTPError as error:
        state = (
            "no_release"
            if error.code == 404
            else "rate_limited"
            if error.code in {403, 429}
            else "unreachable"
        )
        return UpdateInfo(state, repository)
    except (OSError, ValueError, urllib.error.URLError):
        return UpdateInfo("unreachable", repository)


def release_info(data, repository, current):
    repository = github_repository(repository)
    if not isinstance(data, dict):
        return UpdateInfo("invalid_response", repository)
    if data.get("draft") or data.get("prerelease"):
        return UpdateInfo("no_release", repository)
    tag = data.get("tag_name")
    try:
        latest = version_tuple(tag, tag=True)
        installed = version_tuple(current)
    except ValueError:
        return UpdateInfo("invalid_response", repository)
    version = ".".join(str(value) for value in latest)
    # Build a trusted same-repository URL; ignore URLs supplied by the response.
    page = f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}"
    installer = {}
    name = f"MusicCastBridge-{version}-Setup-x64.exe"
    assets = data.get("assets", [])
    if isinstance(assets, list):
        matches = [
            asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name
        ]
        if len(matches) == 1:
            asset = matches[0]
            digest, size = asset.get("digest", ""), asset.get("size")
            if (isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest)
                    and type(size) is int and 0 < size <= _INSTALLER_LIMIT):
                installer = {
                    "installer_url": f"https://github.com/{repository}/releases/download/"
                                     f"{quote(tag, safe='')}/{name}",
                    "installer_sha256": digest[7:].lower(),
                    "installer_size": size,
                }
    return UpdateInfo("available" if latest > installed else "current", repository, version, page,
                      **installer)


def _download_url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in _DOWNLOAD_HOSTS
            or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443)):
        raise UpdateError(tr("GitHub zwrócił nieprawidłowy adres instalatora."))
    return url


class _AssetRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        _download_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def _installer_identity(info):
    repository = github_repository(info.repository)
    version_tuple(info.version)
    expected = f"https://github.com/{repository}/releases/download/"
    name = f"MusicCastBridge-{info.version}-Setup-x64.exe"
    urls = {f"{expected}{tag}/{name}" for tag in (info.version, f"v{info.version}")}
    if (info.state != "available" or info.installer_url not in urls
            or not re.fullmatch(r"[0-9a-f]{64}", info.installer_sha256)
            or type(info.installer_size) is not int
            or not 0 < info.installer_size <= _INSTALLER_LIMIT):
        raise UpdateError(tr("Wydanie nie zawiera instalatora z sumą SHA-256. Otwórz jego stronę."))
    _download_url(info.installer_url)
    return name


def download_update(info, progress=None, cancelled=None):
    """Download only on an explicit action; never execute downloaded bytes here."""
    name = _installer_identity(info)
    folder = config_directory() / "updates"
    folder.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="install-", dir=folder))
    partial, target = staging / "download.part", staging / name
    request = urllib.request.Request(info.installer_url, headers={
        "User-Agent": f"MusicCastBridge/{__version__}", "Accept": "application/octet-stream",
    })
    try:
        opener = urllib.request.build_opener(_AssetRedirect())
        started = time.monotonic()
        digest, received = hashlib.sha256(), 0
        last_percent = -1
        with opener.open(request, timeout=10) as response, partial.open("xb") as output:
            _download_url(response.geturl())
            while chunk := response.read(64 * 1024):
                if cancelled is not None and cancelled.is_set():
                    raise UpdateError(tr("Pobieranie aktualizacji anulowano."))
                received += len(chunk)
                if received > info.installer_size or time.monotonic() - started > 600:
                    raise UpdateError(tr("Pobieranie instalatora przekroczyło dozwolony limit."))
                output.write(chunk)
                digest.update(chunk)
                percent = received * 100 // info.installer_size
                if progress is not None and percent != last_percent:
                    progress(received, info.installer_size)
                    last_percent = percent
        if received != info.installer_size or digest.hexdigest() != info.installer_sha256:
            raise UpdateError(tr("Suma SHA-256 lub rozmiar instalatora nie zgadza się z wydaniem."))
        with partial.open("rb") as downloaded:
            if downloaded.read(2) != b"MZ":
                raise UpdateError(tr("Pobrany plik nie jest instalatorem Windows."))
        partial.replace(target)
        return target
    except (OSError, ValueError, urllib.error.URLError) as error:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(error, UpdateError):
            raise
        raise UpdateError(tr("Nie udało się pobrać instalatora. Spróbuj ponownie.")) from error


def launch_update(path, info):
    """Start a waiting helper; the installer runs only after this app exits."""
    name = _installer_identity(info)
    path = Path(path).resolve()
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError(tr("Instalacja aktualizacji jest dostępna w wersji EXE dla Windows."))
    with path.open("rb") as installer:
        digest = hashlib.file_digest(installer, "sha256").hexdigest()
    if (path.name != name or path.stat().st_size != info.installer_size
            or digest != info.installer_sha256):
        raise UpdateError(tr("Instalator zmienił się po pobraniu. Pobierz aktualizację ponownie."))
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    ready = path.with_suffix(".ready")
    ready.unlink(missing_ok=True)
    process = subprocess.Popen([
        str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(Path(__file__).with_name("update_installer.ps1")),
        "-Installer", str(path), "-ParentProcessId", str(os.getpid()),
        "-InstallDirectory", str(Path(sys.executable).parent),
        "-Language", "polish" if language() == "pl" else "english", "-ReadyFile", str(ready),
    ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=0x08000000)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if ready.exists():
            return
        time.sleep(0.05)
    process.terminate()
    process.wait(timeout=5)
    raise UpdateError(tr("Nie udało się uruchomić instalatora. Spróbuj ponownie."))


def update_text(info):
    if info.state == "available":
        if not info.installer_url:
            return tr(
                "Dostępna jest wersja {version}. Wydanie nie zawiera instalatora z sumą "
                "SHA-256. Otwórz jego stronę.", version=info.version,
            )
        return tr(
            "Dostępna jest wersja {version}. Możesz pobrać i zainstalować ją w aplikacji.",
            version=info.version,
        )
    if info.state == "current":
        return tr("Masz aktualną wersję aplikacji.")
    return {
        "idle": tr("Nie sprawdzono jeszcze aktualizacji."),
        "checking": tr("Sprawdzanie nowych wydań na GitHubie…"),
        "unconfigured": tr(
            "Nie znaleziono adresu repozytorium. Wpisz owner/repo lub zbuduj "
            "aplikację w repozytorium Git z ustawionym remote.origin.url."
        ),
        "invalid_repository": tr(
            "Podaj repozytorium w formacie owner/repo albo https://github.com/owner/repo."
        ),
        "no_release": tr(
            "Brak publicznego stabilnego wydania lub repozytorium jest prywatne. "
            "Sprawdzanie bez logowania wymaga publicznych GitHub Releases."
        ),
        "rate_limited": tr("GitHub ograniczył liczbę zapytań. Spróbuj ponownie później."),
        "unreachable": tr("Nie udało się połączyć z GitHubem. Spróbuj ponownie później."),
        "invalid_response": tr("Nieprawidłowe dane wydania. Wymagany jest stabilny tag vX.Y.Z."),
    }.get(info.state, tr("Nie udało się sprawdzić aktualizacji."))
