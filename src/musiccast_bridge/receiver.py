"""Yamaha Extended Control HTTP client. No retries of commands with side effects."""

import asyncio
import ipaddress
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from .i18n import tr
from .models import Capabilities, ReceiverStatus, Snapshot


class ReceiverError(Exception):
    """An actionable network or Yamaha protocol failure."""


def validate_host(host: str) -> str:
    host = host.strip()
    # Accept a host only: never silently send commands to a path or proxy URL.
    if not host or len(host) > 253 or "/" in host or ":" in host or "@" in host:
        raise ValueError(tr("Wpisz adres IPv4 lub nazwę amplitunera, bez http:// i numeru portu."))
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        labels = host.rstrip(".").split(".")
        if not all(
            re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
            for label in labels
        ):
            raise ValueError(tr("Nieprawidłowy adres amplitunera.")) from None
        if all(label.isdigit() for label in labels):
            raise ValueError(tr("Nieprawidłowy adres IPv4.")) from None
        return host.lower().rstrip(".")
    if address.is_multicast or address.is_unspecified or str(address) == "255.255.255.255":
        raise ValueError(tr("Podaj adres konkretnego amplitunera."))
    return str(address)


class Transport(Protocol):
    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReceiverError(tr("Amplituner przekierował żądanie HTTP. Sprawdź jego adres."))


class HttpTransport:
    def __init__(self, host: str, timeout: float = 3.0):
        self.host = validate_host(host)
        self.timeout = timeout
        # Local receiver traffic must not go through environment-configured proxies.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _get(self, path: str, params: dict[str, Any] | None) -> dict[str, Any]:
        url = f"http://{self.host}/YamahaExtendedControl/v1/{path}"
        if params:
            query = {
                k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in params.items()
            }
            url += "?" + urllib.parse.urlencode(query)
        try:
            with self.opener.open(url, timeout=self.timeout) as response:
                body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise ReceiverError(tr("Odpowiedź urządzenia jest zbyt duża."))
            data = json.loads(body)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ReceiverError(
                tr("Brak odpowiedzi amplitunera. Sprawdź adres, sieć i ustawienie Network Standby.")
            ) from error
        except (ValueError, UnicodeError) as error:
            raise ReceiverError(
                tr("Urządzenie nie zwróciło odpowiedzi MusicCast. Sprawdź adres.")
            ) from error
        if not isinstance(data, dict) or type(data.get("response_code")) is not int:
            raise ReceiverError(tr("Nieprawidłowa odpowiedź API Yamahy."))
        if data["response_code"] != 0:
            reasons = {
                1: tr("błąd wykonania"),
                2: tr("nieprawidłowe żądanie"),
                3: tr("nieznana metoda"),
                4: tr("nieprawidłowy parametr"),
                5: tr("funkcja niedostępna w obecnym stanie"),
            }
            code = data["response_code"]
            raise ReceiverError(tr("Yamaha: {reason} (kod {code}).",
                                   reason=reasons.get(code, tr("błąd urządzenia")), code=code))
        return data

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._get, path, params)


PLAYBACK_BITS = {"play": 0, "stop": 1, "pause": 2, "previous": 3, "next": 4}


class YamahaReceiver:
    def __init__(self, host: str, transport: Transport | None = None):
        self.host = validate_host(host)
        self.transport = transport or HttpTransport(self.host)
        self.capabilities: Capabilities | None = None
        self.name = self.host
        self.model = "Yamaha"
        self.input_names: dict[str, str] = {}
        self.demo = False

    async def connect(self) -> Snapshot:
        # Discovery/connection reads state only; it never wakes or changes the receiver.
        info = await self.transport.get("system/getDeviceInfo")
        features = await self.transport.get("system/getFeatures")
        self.capabilities = Capabilities.parse(features)
        self.model = str(info.get("model_name", "Yamaha"))
        self.name = self.model
        try:
            names = await self.transport.get("system/getNameText")
            self.input_names = {
                item["id"]: item["text"]
                for item in names.get("input", [])
                if "id" in item and "text" in item
            }
        except ReceiverError:
            pass  # Optional on older firmware.
        return await self.refresh()

    async def refresh(self) -> Snapshot:
        if self.capabilities is None:
            raise ReceiverError(tr("Najpierw połącz aplikację z amplitunerem."))
        status = ReceiverStatus.parse(await self.transport.get("main/getStatus"))
        play_info: dict[str, Any] = {}
        if status.power == "on" and status.input in {
            "server",
            "usb",
            "net_radio",
            "spotify",
            "airplay",
            "tidal",
            "deezer",
            "napster",
        }:
            try:
                play_info = await self.transport.get("netusb/getPlayInfo")
            except ReceiverError:
                pass
        return Snapshot(
            self.host,
            self.name,
            self.model,
            self.capabilities,
            status,
            self.input_names,
            play_info,
            self.demo,
        )

    def require(self, function: str):
        if self.capabilities is None or function not in self.capabilities.functions:
            raise ReceiverError(tr("Amplituner nie zgłasza obsługi tej funkcji."))

    async def set_power(self, power: str) -> Snapshot:
        self.require("power")
        if power not in {"on", "standby"}:
            raise ValueError(tr("Nieprawidłowy stan zasilania."))
        await self.transport.get("main/setPower", {"power": power})
        return await self.refresh()

    async def set_mute(self, enable: bool) -> Snapshot:
        self.require("mute")
        status = ReceiverStatus.parse(await self.transport.get("main/getStatus"))
        if status.disable_flags & 2:
            raise ReceiverError(tr("Wyciszenie jest obecnie niedostępne."))
        await self.transport.get("main/setMute", {"enable": enable})
        return await self.refresh()

    async def set_volume(self, percent: int) -> Snapshot:
        self.require("volume")
        if self.capabilities.volume is None:
            raise ReceiverError(tr("Brak zakresu regulacji głośności."))
        # Re-read ceiling at command time: another controller can change Max Volume.
        status = ReceiverStatus.parse(await self.transport.get("main/getStatus"))
        if status.disable_flags & 1:
            raise ReceiverError(tr("Regulacja głośności jest obecnie niedostępna."))
        value = self.capabilities.volume.from_percent(percent, status.max_volume)
        await self.transport.get("main/setVolume", {"volume": value})
        return await self.refresh()

    async def step_volume(self, direction: int) -> Snapshot:
        self.require("volume")
        if direction not in {-1, 1}:
            raise ValueError(tr("Kierunek zmiany głośności musi wynosić -1 albo 1."))
        bounds = self.capabilities.volume
        status = ReceiverStatus.parse(await self.transport.get("main/getStatus"))
        if bounds is None or status.volume is None or status.disable_flags & 1:
            raise ReceiverError(tr("Regulacja głośności jest obecnie niedostępna."))
        value = bounds.normalize(status.volume + direction * bounds.step, status.max_volume)
        await self.transport.get("main/setVolume", {"volume": value})
        return await self.refresh()

    async def set_input(self, input_id: str) -> Snapshot:
        if self.capabilities is None or input_id not in self.capabilities.inputs:
            raise ReceiverError(tr("Amplituner nie zgłasza takiego źródła."))
        await self.transport.get("main/setInput", {"input": input_id})
        return await self.refresh()

    async def playback(self, action: str) -> Snapshot:
        if action not in PLAYBACK_BITS:
            raise ValueError(tr("Nieprawidłowe polecenie odtwarzania."))
        snapshot = await self.refresh()
        if not int(snapshot.play_info.get("attribute", 0)) & (1 << PLAYBACK_BITS[action]):
            raise ReceiverError(tr("Bieżące źródło nie udostępnia tego polecenia odtwarzania."))
        await self.transport.get("netusb/setPlayback", {"playback": action})
        return await self.refresh()
