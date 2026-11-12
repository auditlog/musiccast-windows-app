"""First-run installer preferences and a Windows marker protecting app upgrades."""

import configparser
import ctypes
import sys
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path

APP_MUTEX = "Local\\MusicCastBridge.App"


def is_standard_cable_name(name):
    folded = name.casefold().strip()
    return folded.startswith("cable input (") and "vb-audio" in folded


def prefer_installed_cable():
    if not getattr(sys, "frozen", False):
        return False
    config = configparser.ConfigParser()
    try:
        config.read(Path(sys.executable).parent / "install.ini", encoding="utf-8")
        return config.getboolean("Audio", "PreferCable", fallback=False)
    except (OSError, ValueError, configparser.Error):
        return False


def installed_language_selection():
    if not getattr(sys, "frozen", False):
        return "pl", ""
    config = configparser.ConfigParser()
    try:
        config.read(Path(sys.executable).parent / "install.ini", encoding="utf-8")
        selected = config.get("General", "Language", fallback="polish")
        marker = config.get("General", "LanguageSelection", fallback="")[:128]
        return ("en" if selected == "english" else "pl"), marker
    except (OSError, ValueError, configparser.Error):
        return "pl", ""


def installed_language():
    return installed_language_selection()[0]


@contextmanager
def application_marker():
    """Keep Inno's AppMutex present while the app runs; no audio/device changes."""
    if sys.platform != "win32":
        yield
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateMutexW(None, False, APP_MUTEX)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.CloseHandle(handle)
