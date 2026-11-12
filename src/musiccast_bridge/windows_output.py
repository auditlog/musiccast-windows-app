"""Opt-in playback routing with conditional rollback and crash recovery.

The helper uses Core Audio for enumeration and the Windows IPolicyConfig COM
interface for switching. The latter is not a public Microsoft API: failures
must abort startup, never silently capture another output. Communications and
capture/microphone defaults are never changed.
"""

import asyncio
import ctypes
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from .i18n import tr
from .settings import config_directory

log = logging.getLogger(__name__)


class OutputError(Exception):
    pass


class WindowsOutput:
    def __init__(self):
        self._lease = None

    def claim(self):
        if sys.platform != "win32":
            raise OutputError(tr("Automatyczne wyjście dźwięku jest dostępne tylko w Windows."))
        if self._lease:
            return
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateMutexW(None, False, "Local\\MusicCastBridge.AudioRoute")
        if not handle:
            raise OutputError(tr("Nie udało się zablokować trasy dźwięku Windows."))
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle(handle)
            raise OutputError(tr("Inna instancja MusicCast Bridge korzysta z automatycznej trasy."))
        self._lease = handle

    def release(self):
        if self._lease:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(self._lease)
            self._lease = None

    def query(self):
        return self._run({"operation": "list"})

    def select(self, endpoint, roles):
        return self._run({"operation": "select", "endpoint": endpoint, "roles": list(roles)})

    def _run(self, request):
        if sys.platform != "win32":
            raise OutputError(tr("Automatyczne wyjście dźwięku jest dostępne tylko w Windows."))
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
            "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        try:
            result = subprocess.run(
                [
                    str(powershell),
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(Path(__file__).with_name("windows_output.ps1")),
                ],
                input=json.dumps(request),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=True,
                creationflags=0x08000000,
            )
            if len(result.stdout) > 1_000_000:
                raise ValueError("oversized response")
            data = json.loads(result.stdout.lstrip("\ufeff"))
            if not isinstance(data.get("devices"), list) or not isinstance(
                data.get("defaults"), dict
            ):
                raise ValueError("invalid response")
            return data
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            if isinstance(error, subprocess.CalledProcessError):
                log.error("Windows output helper failed: %s", (error.stderr or "")[:4000])
            raise OutputError(
                tr(
                    "Nie udało się odczytać lub zmienić wyjścia Windows. Sprawdź urządzenie w"
                    " ustawieniach dźwięku Windows."
                )
            ) from error


class OutputRoute:
    def __init__(self, backend=None, path=None):
        self.backend = backend or WindowsOutput()
        self.path = path or config_directory() / "audio-route.json"
        self._lock = asyncio.Lock()
        self._owned = False

    async def _complete(self, operation):
        # A cancelled startup must wait for its system mutation before rollback.
        task = asyncio.create_task(asyncio.to_thread(operation))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def begin(self, endpoint):
        async with self._lock:
            try:
                await self._complete(lambda: self._begin(endpoint))
            except BaseException:
                await self._complete(self._restore)
                raise

    async def restore(self, recover=False):
        async with self._lock:
            if self._owned or recover:
                await self._complete(self._restore)

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid journal")
        except (OSError, ValueError) as error:
            raise OutputError(tr(
                "Zapis poprzedniego wyjścia jest uszkodzony. Wybierz wyjście w Windows."
            )) from error
        previous = data.get("previous")
        if (
            not isinstance(data.get("target"), str)
            or not isinstance(previous, dict)
            or not previous
            or set(previous) - {"0", "1"}
            or any(not isinstance(value, str) or not value for value in previous.values())
        ):
            raise OutputError(
                tr("Zapis poprzedniego wyjścia jest uszkodzony. Wybierz wyjście w Windows.")
            )
        return data

    def _begin(self, endpoint):
        self.backend.claim()
        self._owned = True
        if self.path.exists():
            self._restore(release=False)
        state = self.backend.query()
        if endpoint not in {item["id"] for item in state["devices"]}:
            raise OutputError(
                tr("Wybrane wyjście Windows jest niedostępne. Wybierz je w ustawieniach.")
            )
        previous = {role: state["defaults"].get(role) for role in ("0", "1")}
        if not all(previous.values()):
            raise OutputError(tr("Windows nie zgłosił poprzedniego wyjścia. Nie zmieniono trasy."))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"target": endpoint, "previous": previous}), encoding="utf-8"
        )
        temporary.replace(self.path)
        selected = self.backend.select(endpoint, previous)
        if any(selected["defaults"].get(role) != endpoint for role in previous):
            raise OutputError(tr("Windows nie potwierdził zmiany wyjścia dźwięku."))

    def _restore(self, release=True):
        try:
            if not self.path.exists():
                return
            self.backend.claim()
            data = self._read()
            state = self.backend.query()
            available = {item["id"] for item in state["devices"]}
            for role, previous in data["previous"].items():
                # Respect manual changes made while listening.
                if state["defaults"].get(role) != data["target"]:
                    continue
                if previous not in available:
                    raise OutputError(
                        tr(
                            "Poprzednie wyjście jest odłączone. Podłącz je i kliknij „Przywróć "
                            "wyjście” w ustawieniach lub wybierz urządzenie w Windows."
                        )
                    )
                state = self.backend.select(previous, [role])
                if state["defaults"].get(role) != previous:
                    raise OutputError(
                        tr("Windows nie potwierdził przywrócenia poprzedniego wyjścia.")
                    )
            self.path.unlink()
        finally:
            if release:
                self.backend.release()
                self._owned = False
