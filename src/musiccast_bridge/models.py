"""Receiver capabilities, parsed without assuming any model-specific volume scale."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .i18n import tr


@dataclass(frozen=True)
class VolumeRange:
    minimum: int
    maximum: int
    step: int = 1

    def __post_init__(self):
        if self.maximum <= self.minimum or self.step <= 0:
            raise ValueError(tr("Nieprawidłowy zakres głośności zwrócony przez amplituner."))

    def normalize(self, value: int, ceiling: int | None = None) -> int:
        upper = min(self.maximum, ceiling if ceiling is not None else self.maximum)
        upper = max(self.minimum, upper)
        value = max(self.minimum, min(value, upper))
        steps = (Decimal(value - self.minimum) / self.step).to_integral_value(
            rounding=ROUND_HALF_UP
        )
        result = self.minimum + int(steps) * self.step
        if result > upper:
            result = self.minimum + ((upper - self.minimum) // self.step) * self.step
        return result

    def from_percent(self, percent: int, ceiling: int | None = None) -> int:
        if not 0 <= percent <= 100:
            raise ValueError(tr("Głośność musi mieścić się w zakresie 0–100%."))
        raw = self.minimum + round((self.maximum - self.minimum) * percent / 100)
        return self.normalize(raw, ceiling)

    def to_percent(self, value: int) -> int:
        return max(0, min(100, round(100 * (value - self.minimum) / (self.maximum - self.minimum))))


@dataclass(frozen=True)
class Capabilities:
    inputs: tuple[str, ...]
    functions: frozenset[str]
    volume: VolumeRange | None
    system_functions: frozenset[str] = frozenset()

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Capabilities":
        zone = next((z for z in data.get("zone", []) if z.get("id") == "main"), None)
        if zone is None:
            raise ValueError(tr("Urządzenie nie udostępnia głównej strefy MusicCast."))
        volume = next((r for r in zone.get("range_step", []) if r.get("id") == "volume"), None)
        return cls(
            inputs=tuple(zone.get("input_list", [])),
            functions=frozenset(zone.get("func_list", [])),
            volume=VolumeRange(int(volume["min"]), int(volume["max"]), int(volume["step"]))
            if volume
            else None,
            system_functions=frozenset(data.get("system", {}).get("func_list", [])),
        )


@dataclass(frozen=True)
class ReceiverStatus:
    power: str
    volume: int | None
    mute: bool
    input: str
    max_volume: int | None = None
    volume_display: str | None = None
    disable_flags: int = 0

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "ReceiverStatus":
        actual = data.get("actual_volume", {})
        display = None
        if isinstance(actual, dict) and isinstance(actual.get("value"), (int, float)):
            display = f"{actual['value']:g} {actual.get('unit', '')}".strip()
        return cls(
            power=data.get("power", "unknown"),
            volume=data.get("volume"),
            mute=bool(data.get("mute", False)),
            input=data.get("input", ""),
            max_volume=data.get("max_volume"),
            volume_display=display,
            disable_flags=int(data.get("disable_flags", 0)),
        )


@dataclass(frozen=True)
class Snapshot:
    host: str
    name: str
    model: str
    capabilities: Capabilities
    status: ReceiverStatus
    input_names: dict[str, str] = field(default_factory=dict)
    play_info: dict[str, Any] = field(default_factory=dict)
    demo: bool = False


INPUT_NAMES = {
    "airplay": "AirPlay",
    "spotify": "Spotify",
    "bluetooth": "Bluetooth",
    "net_radio": "Radio internetowe",
    "server": "Serwer / DLNA",
    "usb": "USB",
    "tuner": "Radio FM/AM",
    "cd": "CD",
    "phono": "Gramofon",
    "optical1": "Optyczne 1",
    "optical2": "Optyczne 2",
    "coaxial1": "Koaksjalne 1",
    "coaxial2": "Koaksjalne 2",
    "line1": "Line 1",
    "line2": "Line 2",
    "line3": "Line 3",
}


def input_label(input_id: str) -> str:
    return tr(INPUT_NAMES.get(input_id, input_id.replace("_", " ").title()))
