"""Small local settings file. Does not contain credentials or captured audio."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .installation import installed_language_selection, prefer_installed_cable


def config_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_CONFIG_HOME")
    return Path(base or Path.home() / ".config") / "MusicCastBridge"


@dataclass
class Settings:
    host: str = ""
    close_to_tray: bool = True
    # Device indices change after reboot. Restore a unique device name instead.
    audio_device_name: str = ""
    prefer_virtual_cable: bool = False
    language: str = "pl"
    auto_output: bool = False
    windows_output_id: str = ""
    windows_output_name: str = ""
    check_updates_at_startup: bool = True
    update_repository: str = ""
    installer_language_selection: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_directory() / "settings.json"
        installed_language, selection = installed_language_selection()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            host = data.get("host", "")
            if not isinstance(host, str):
                raise ValueError("Invalid settings host")
            device = data.get("audio_device_name", "")
            settings = cls(
                host=host[:253],
                close_to_tray=bool(data.get("close_to_tray", True)),
                audio_device_name=device[:512] if isinstance(device, str) else "",
                prefer_virtual_cable=data.get("prefer_virtual_cable") is True,
                language="en" if data.get("language") == "en" else "pl",
                auto_output=data.get("auto_output") is True,
                windows_output_id=_text(data.get("windows_output_id"), 512),
                windows_output_name=_text(data.get("windows_output_name"), 512),
                check_updates_at_startup=data.get("check_updates_at_startup", True) is True,
                update_repository=_text(data.get("update_repository"), 300),
                installer_language_selection=_text(data.get("installer_language_selection"), 128),
            )
            if selection and selection != settings.installer_language_selection:
                settings.language = installed_language
                settings.installer_language_selection = selection
            return settings
        except (OSError, ValueError, AttributeError):
            return cls(prefer_virtual_cable=prefer_installed_cable(), language=installed_language,
                       installer_language_selection=selection)

    def save(self, path: Path | None = None):
        path = path or config_directory() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, delete=False
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(asdict(self), handle, ensure_ascii=False, indent=2)
            temp_path.replace(path)
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)


def _text(value, limit):
    return value[:limit] if isinstance(value, str) else ""
