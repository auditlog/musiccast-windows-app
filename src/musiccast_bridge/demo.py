"""Explicit synthetic receiver, never used as a fallback for connection errors."""

import copy
from typing import Any

from .i18n import tr
from .receiver import ReceiverError, YamahaReceiver


class DemoTransport:
    def __init__(self):
        self.status = {
            "power": "on",
            "volume": 60,
            "mute": False,
            "input": "spotify",
            "max_volume": 140,
            "disable_flags": 0,
        }
        self.track = 0
        self.playing = True

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if path == "system/getDeviceInfo":
            result = {"model_name": tr("R-N602 · demonstracja")}
        elif path == "system/getFeatures":
            result = {
                "system": {"func_list": ["network_standby"]},
                "zone": [
                    {
                        "id": "main",
                        "func_list": ["power", "volume", "mute"],
                        "input_list": [
                            "spotify",
                            "airplay",
                            "bluetooth",
                            "net_radio",
                            "server",
                            "usb",
                            "cd",
                            "line1",
                            "line2",
                            "line3",
                            "optical1",
                            "optical2",
                            "phono",
                        ],
                        "range_step": [{"id": "volume", "min": 0, "max": 161, "step": 1}],
                    }
                ],
            }
        elif path == "system/getNameText":
            result = {"input": []}
        elif path == "main/getStatus":
            result = copy.deepcopy(self.status)
            result["actual_volume"] = {
                "mode": "db",
                "value": -80 + result["volume"] * 0.5,
                "unit": "dB",
            }
        elif path == "netusb/getPlayInfo":
            result = {
                "track": [tr("Wieczorny odsłuch"), tr("Drugi utwór")][self.track % 2],
                "artist": tr("Dane demonstracyjne"),
                "attribute": 31,
                "playback": "play" if self.playing else "pause",
            }
        elif path == "main/setPower":
            self.status["power"] = params["power"]
            result = {}
        elif path == "main/setVolume":
            self.status["volume"] = params["volume"]
            result = {}
        elif path == "main/setMute":
            self.status["mute"] = params["enable"]
            result = {}
        elif path == "main/setInput":
            self.status["input"] = params["input"]
            result = {}
        elif path == "netusb/setPlayback":
            action = params["playback"]
            if action in {"next", "previous"}:
                self.track += 1
            else:
                self.playing = action == "play"
            result = {}
        else:
            raise ReceiverError(tr("Nieobsługiwane polecenie trybu demonstracyjnego."))
        return {"response_code": 0, **result}


def demo_receiver() -> YamahaReceiver:
    receiver = YamahaReceiver("demo.local", DemoTransport())
    receiver.demo = True
    return receiver
