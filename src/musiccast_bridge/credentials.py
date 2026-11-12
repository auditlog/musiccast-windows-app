"""Per-receiver AirPlay secrets in the current user's Windows Credential Manager."""

import ctypes
import logging
import sys
from ctypes import wintypes
from functools import cache

log = logging.getLogger(__name__)

_GENERIC = 1  # CRED_TYPE_GENERIC
_LOCAL_MACHINE = 2  # CRED_PERSIST_LOCAL_MACHINE
_NOT_FOUND = 1168  # ERROR_NOT_FOUND
_MAX_BLOB_SIZE = 2560


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_CredentialPointer = ctypes.POINTER(_Credential)


@cache
def _windows_api():
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_CredentialPointer)
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [_CredentialPointer, wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    return api


class AirPlayCredentials:
    def __init__(self):
        self._session: dict[str, str | None] = {}

    def read(self, identifier: str | None, kind: str) -> str | None:
        if not identifier:
            return None
        target = f"MusicCastBridge/AirPlay/{kind}/{identifier.lower()}"
        if target in self._session or sys.platform != "win32":
            return self._session.get(target)
        try:
            api = _windows_api()
            result = _CredentialPointer()
            if not api.CredReadW(target, _GENERIC, 0, ctypes.byref(result)):
                code = ctypes.get_last_error()
                if code == _NOT_FOUND:
                    return None
                raise ctypes.WinError(code)
            try:
                blob = result.contents
                if blob.CredentialBlob and 0 < blob.CredentialBlobSize <= _MAX_BLOB_SIZE:
                    return ctypes.string_at(blob.CredentialBlob, blob.CredentialBlobSize).decode()
            finally:
                api.CredFree(result)
        except (OSError, UnicodeError):
            log.warning("Could not read AirPlay credentials from Windows Credential Manager")
        return None

    def write(self, identifier: str | None, kind: str, value: str | None):
        if not identifier:
            return
        target = f"MusicCastBridge/AirPlay/{kind}/{identifier.lower()}"
        self._session[target] = value
        if sys.platform != "win32":
            return
        try:
            api = _windows_api()
            if value is None:
                if not api.CredDeleteW(target, _GENERIC, 0):
                    code = ctypes.get_last_error()
                    if code != _NOT_FOUND:
                        raise ctypes.WinError(code)
                return
            data = value.encode()
            if len(data) > _MAX_BLOB_SIZE:
                raise ValueError("Credential exceeds Windows storage limit")
            buffer = (wintypes.BYTE * len(data)).from_buffer_copy(data)
            credential = _Credential(
                Type=_GENERIC,
                TargetName=target,
                CredentialBlobSize=len(data),
                CredentialBlob=buffer,
                Persist=_LOCAL_MACHINE,
            )
            if not api.CredWriteW(ctypes.byref(credential), 0):
                raise ctypes.WinError(ctypes.get_last_error())
        except (OSError, ValueError):
            log.warning("Could not update AirPlay credentials in Windows Credential Manager")
