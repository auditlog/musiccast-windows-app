import struct
import unittest

from musiccast_bridge.diagnostics import health_summary
from musiccast_bridge.health import CaptureMeter


class HealthTests(unittest.TestCase):
    def test_levels_use_all_samples_and_reset_interval(self):
        meter = CaptureMeter()
        meter.record(struct.pack("<hhhh", 16384, -16384, 0, 0), now=10)
        meter.record(bytes(8), now=10.025)
        result = meter.snapshot(now=10.03)
        self.assertEqual(result["capture_peak_dbfs"], -6.0)
        self.assertEqual(result["capture_rms_dbfs"], -12.0)
        self.assertEqual(result["capture_max_gap_ms"], 25.0)
        self.assertEqual(result["capture_idle_ms"], 5.0)
        self.assertEqual(result["capture_samples"], 8)
        result = meter.snapshot(now=11)
        self.assertIsNone(result["capture_peak_dbfs"])
        self.assertEqual(result["capture_samples"], 0)
        self.assertEqual(result["capture_max_gap_ms"], 25.0)
        self.assertEqual(result["capture_idle_ms"], 975.0)

    def test_silence_and_boundary_samples_are_distinguished(self):
        meter = CaptureMeter()
        meter.record(bytes(16))
        self.assertIsNone(meter.snapshot()["capture_rms_dbfs"])
        meter.record(struct.pack("<hhh", 32767, -32768, 100))
        result = meter.snapshot()
        self.assertEqual(result["capture_peak_dbfs"], 0)
        self.assertEqual(result["capture_clipped_samples"], 2)

    def test_summary_reports_local_measurements_without_delivery_percentage(self):
        report = '\n'.join([
            'null', 'not json',
            '{"event":"stream_health", "capture_peak_dbfs":-20.1, "requested_packets":5,'
            '"retransmitted_packets":3, "retransmit_unavailable":2, "inserted_silence_ms":40}',
            '{"event":"receiver_state", "volume":40}',
        ])
        result = health_summary(report)
        self.assertIn("-20.1 dBFS", result)
        self.assertIn("wysłane ponownie: 3", result)
        self.assertIn("brak w buforze: 2", result)
        self.assertIn("40 ms", result)
        self.assertNotIn("%", result)
