"""Bounded, thread-safe AirPlay diagnostics with an explicit set of report fields."""

import json
import logging
import platform
import threading
import time
from collections import deque
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from .i18n import tr

log = logging.getLogger(__name__)


def health_summary(report):
    for line in reversed(report.splitlines()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("event") == "stream_health":
            peak = row.get("capture_peak_dbfs")
            level = (
                tr("szczyt {v0:g} dBFS", v0=peak)
                if peak is not None
                else tr("cisza")
                if row.get("capture_samples", 0)
                else tr("brak pomiaru")
            )
            return tr(
                "Źródło: {v0}. Żądane pakiety: {v1}, wysłane ponownie: {v2}, brak w "
                "buforze: {v3}. Dodana cisza: {v4:g} ms.",
                v0=level,
                v1=row.get("requested_packets", 0),
                v2=row.get("retransmitted_packets", 0),
                v3=row.get("retransmit_unavailable", 0),
                v4=row.get("inserted_silence_ms", 0),
            )
    return tr("Pomiary pojawią się po kilku sekundach przesyłania.")


_FIELDS = {
    "attempt",
    "profile",
    "operation",
    "cseq",
    "code",
    "ms",
    "error",
    "host",
    "port",
    "local_ip",
    "remote_ip",
    "control_port",
    "timing_port",
    "server_port",
    "rate",
    "channels",
    "buffered_bytes",
    "dropped_bytes",
    "peak",
    "timing_requests",
    "timing_replies",
    "control_packets",
    "audio_packets",
    "audio_bytes",
    "source",
    "state",
    "password_present",
    "paired",
    "reason",
    "retry_in",
    "outcome",
    "python",
    "pyatv",
    "platform",
    "frames",
    "session_present",
    "rtp_seq",
    "rtp_time",
    "airplay_version",
    "power",
    "input",
    "mute",
    "volume",
    "capture_frames",
    "capture_status_flags",
    "device_index",
    "remote_control_port",
    "remote_timing_port",
    "sample_bits",
    "encoding",
    "retransmit_requests",
    "requested_packets",
    "retransmitted_packets",
    "retransmit_unavailable",
    "retransmit_send_errors",
    "ignored_udp_packets",
    "max_send_gap_ms",
    "send_gaps_over_50ms",
    "capture_peak_dbfs",
    "capture_rms_dbfs",
    "capture_clipped_samples",
    "capture_max_gap_ms",
    "capture_samples",
    "capture_idle_ms",
    "inserted_silence_bytes",
    "inserted_silence_ms",
    "underflow_reads",
    "delivery_confirmed",
    "retransmitted_bytes",
    "buffered_ms",
}


class AirPlayDiagnostics:
    def __init__(self):
        self._lock = threading.Lock()
        self._lines: deque[str] = deque(maxlen=500)
        self._run = ""
        self._counts: dict[str, int | float] = {}
        self._live = {"state": "idle", "run": "", "attempt": 0}
        self.failure_operation: str | None = None
        self.instrumented = False
        self.airplay_version: int | None = None

    def start(self, host, source):
        with self._lock:
            self._run = uuid4().hex[:10]
            self._lines.clear()
            self._counts.clear()
            self._live = {"state": "connecting", "run": self._run, "attempt": 0}
        try:
            pyatv_version = version("pyatv")
        except PackageNotFoundError:
            pyatv_version = "unavailable"
        self.emit(
            "session_started",
            host=host,
            source=source,
            python=platform.python_version(),
            platform=platform.system(),
            pyatv=pyatv_version,
        )

    def attempt(self, number, profile):
        with self._lock:
            self._counts = dict.fromkeys(
                (
                    "timing_requests",
                    "timing_replies",
                    "control_packets",
                    "audio_packets",
                    "audio_bytes",
                    "retransmit_requests",
                    "requested_packets",
                    "retransmitted_packets",
                    "retransmitted_bytes",
                    "retransmit_unavailable",
                    "retransmit_send_errors",
                    "ignored_udp_packets",
                    "max_send_gap_ms",
                    "send_gaps_over_50ms",
                ),
                0,
            )
            self._live = {
                "state": "connecting",
                "run": self._run,
                "attempt": number,
            }
        self.failure_operation = None
        self.instrumented = False
        self.airplay_version = None
        self.emit("attempt_started", attempt=number, profile=profile)

    def emit(self, event, **fields):
        # Only scalar technical fields are accepted. Raw headers, bodies, credentials,
        # metadata and captured samples never enter the diagnostic report.
        safe = {
            key: value
            for key, value in fields.items()
            if key in _FIELDS and isinstance(value, (str, int, float, bool, type(None)))
        }
        row = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "run": self._run,
            "event": event,
            **safe,
        }
        line = json.dumps(row, ensure_ascii=False)
        with self._lock:
            self._lines.append(line)
            if event == "sender_ready":
                self._live.update(state="playing", sampled_at=time.monotonic())
            elif event == "recovery_scheduled":
                self._live.update(state="connecting", sampled_at=None)
            elif event in {"session_stopped", "session_cancelled", "session_failed"}:
                self._live["state"] = "stopped"
        log.info("%s", line)

    def count(self, name, amount=1):
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + amount
            return self._counts[name]

    def counters(self):
        with self._lock:
            return dict(self._counts)

    def maximum(self, name, value):
        with self._lock:
            self._counts[name] = max(self._counts.get(name, 0), value)

    def publish(self, **fields):
        """Publish scalar source measurements without producing another log row."""
        with self._lock:
            self._live.update(
                {
                    name: value
                    for name, value in fields.items()
                    if name in _FIELDS and isinstance(value, (int, float, type(None)))
                }
            )
            self._live["sampled_at"] = time.monotonic()

    def snapshot(self):
        with self._lock:
            return {**self._live, **self._counts}

    def report(self):
        with self._lock:
            return "\n".join(self._lines)
