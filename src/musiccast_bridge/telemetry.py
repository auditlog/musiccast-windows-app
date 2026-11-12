"""Passive stream traffic rates; no link-capacity or playback-delivery estimates."""

import time
from dataclasses import dataclass

from .i18n import language, tr

_RATE_COUNTERS = (
    "audio_bytes",
    "audio_packets",
    "retransmitted_bytes",
    "retransmitted_packets",
)


@dataclass(frozen=True)
class TrafficView:
    state: str
    audio_mbps: float | None = None
    audio_pps: float | None = None
    resend_mbps: float | None = None
    resend_pps: float | None = None
    resent_total: int = 0
    unavailable: int = 0
    send_errors: int = 0
    buffered_ms: float | None = None
    silence_ms: float | None = None
    max_gap_ms: float | None = None


class TrafficMonitor:
    def __init__(self):
        self._previous = None
        self._previous_time = None

    def sample(self, snapshot, now=None):
        now = time.monotonic() if now is None else now
        previous = self._previous
        elapsed = now - self._previous_time if self._previous_time is not None else 0
        same_attempt = previous is not None and (snapshot.get("run"), snapshot.get("attempt")) == (
            previous.get("run"),
            previous.get("attempt"),
        )
        playing = snapshot.get("state") == "playing"
        sampled_at = snapshot.get("sampled_at")
        stale = playing and (sampled_at is None or now - sampled_at > 3)
        valid_rate = (
            playing
            and not stale
            and same_attempt
            and elapsed > 0
            and previous.get("state") == "playing"
            and all(snapshot.get(key, 0) >= previous.get(key, 0) for key in _RATE_COUNTERS)
        )
        rates = (
            {key: (snapshot.get(key, 0) - previous.get(key, 0)) / elapsed for key in _RATE_COUNTERS}
            if valid_rate
            else {}
        )
        self._previous = dict(snapshot)
        self._previous_time = now
        state = (
            tr("Pomiar nieaktualny")
            if stale
            else tr("Przesyłanie")
            if playing
            else tr("Łączenie…")
            if snapshot.get("state") == "connecting"
            else tr("Zatrzymana")
            if snapshot.get("state") == "stopped"
            else tr("Nieaktywna")
        )
        return TrafficView(
            state=state,
            audio_mbps=rates["audio_bytes"] * 8 / 1_000_000 if rates else None,
            audio_pps=rates.get("audio_packets"),
            resend_mbps=rates["retransmitted_bytes"] * 8 / 1_000_000 if rates else None,
            resend_pps=rates.get("retransmitted_packets"),
            resent_total=snapshot.get("retransmitted_packets", 0),
            unavailable=snapshot.get("retransmit_unavailable", 0),
            send_errors=snapshot.get("retransmit_send_errors", 0),
            buffered_ms=snapshot.get("buffered_ms") if playing and not stale else None,
            silence_ms=snapshot.get("inserted_silence_ms") if playing and not stale else None,
            max_gap_ms=snapshot.get("max_send_gap_ms") if playing and not stale else None,
        )


def traffic_text(view):
    def number(value, decimals=0):
        if value is None:
            return "—"
        result = f"{value:.{decimals}f}"
        return result if language() == "en" else result.replace(".", ",")

    return {
        "audio": tr(
            "{v0} Mb/s · {v1} pak./s", v0=number(view.audio_mbps, 2), v1=number(view.audio_pps, 1)
        ),
        "resends": (
            tr(
                "{v0} Mb/s · {v1} pak./s · {v2} razem",
                v0=number(view.resend_mbps, 2),
                v1=number(view.resend_pps, 1),
                v2=view.resent_total,
            )
        ),
        "buffer": tr(
            "{v0} ms · cisza {v1} ms", v0=number(view.buffered_ms), v1=number(view.silence_ms)
        ),
        "errors": tr("{v0} brak w buforze · {v1} błędów", v0=view.unavailable, v1=view.send_errors),
        "gap": f"{number(view.max_gap_ms, 1)} ms max.",
    }
