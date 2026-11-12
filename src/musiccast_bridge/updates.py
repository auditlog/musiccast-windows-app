"""Read-only GitHub release checks. Never downloads or launches an installer."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import quote

from . import __version__
from .i18n import tr
from .versioning import default_update_repository, github_repository, version_tuple

_LIMIT = 1_048_576


@dataclass(frozen=True)
class UpdateInfo:
    state: str = "idle"
    repository: str = ""
    version: str = ""
    release_url: str = ""


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
    return UpdateInfo("available" if latest > installed else "current", repository, version, page)


def update_text(info):
    if info.state == "available":
        return tr(
            "Dostępna jest wersja {version}. Otwórz wydanie i pobierz instalator.",
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
