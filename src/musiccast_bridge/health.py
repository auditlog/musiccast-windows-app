"""Audio measurements without retaining samples or claiming receiver delivery."""

import math
import threading
import time


def dbfs(value):
    return round(20 * math.log10(value), 1) if value > 0 else None


class CaptureMeter:
    """Bounded, thread-safe interval levels and cumulative capture timing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._peak = 0
        self._energy = 0
        self._samples = 0
        self._clipped = 0
        self._previous = None
        self._max_gap = 0.0

    def record(self, pcm, now=None):
        now = time.monotonic() if now is None else now
        values = memoryview(pcm).cast("h")
        peak = max((abs(value) for value in values), default=0)
        energy = sum(value * value for value in values)
        clipped = sum(value >= 32767 or value <= -32768 for value in values)
        with self._lock:
            if self._previous is not None:
                self._max_gap = max(self._max_gap, (now - self._previous) * 1000)
            self._previous = now
            self._peak = max(self._peak, peak)
            self._energy += energy
            self._samples += len(values)
            self._clipped += clipped
        return peak / 32768

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            rms = math.sqrt(self._energy / self._samples) / 32768 if self._samples else 0
            result = {
                "capture_peak_dbfs": dbfs(self._peak / 32768),
                "capture_rms_dbfs": dbfs(rms),
                "capture_clipped_samples": self._clipped,
                "capture_max_gap_ms": round(self._max_gap, 1),
                "capture_samples": self._samples,
                "capture_idle_ms": (
                    round(max(0, (now - self._previous) * 1000), 1)
                    if self._previous is not None else None
                ),
            }
            self._peak = self._energy = self._samples = self._clipped = 0
            return result
