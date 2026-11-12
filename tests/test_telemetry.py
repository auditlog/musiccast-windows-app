import unittest

from musiccast_bridge.telemetry import TrafficMonitor, traffic_text


def reading(**changes):
    return {
        "run": "test-run", "attempt": 1, "state": "playing", "sampled_at": 10,
        "audio_bytes": 0, "audio_packets": 0, "retransmitted_bytes": 0,
        "retransmitted_packets": 0, "retransmit_unavailable": 0,
        "retransmit_send_errors": 0, "buffered_ms": 120, "inserted_silence_ms": 0,
        "max_send_gap_ms": 14.1, **changes,
    }


class TrafficTests(unittest.TestCase):
    def test_rates_use_real_elapsed_time_and_separate_resends(self):
        monitor = TrafficMonitor()
        self.assertIsNone(monitor.sample(reading(), now=10).audio_mbps)
        view = monitor.sample(reading(
            sampled_at=12, audio_bytes=355000, audio_packets=250,
            retransmitted_bytes=5696, retransmitted_packets=4,
        ), now=12)
        self.assertAlmostEqual(view.audio_mbps, 1.42)
        self.assertEqual(view.audio_pps, 125)
        self.assertAlmostEqual(view.resend_mbps, 0.022784)
        self.assertEqual(view.resend_pps, 2)
        self.assertEqual(view.resent_total, 4)
        self.assertEqual(view.buffered_ms, 120)
        text = traffic_text(view)
        self.assertIn("1,42 Mb/s", text["audio"])
        self.assertIn("125,0 pak./s", text["audio"])
        self.assertNotIn("%", " ".join(text.values()))

    def test_recovery_or_new_run_restarts_measurement_without_spikes(self):
        monitor = TrafficMonitor()
        monitor.sample(reading(audio_bytes=1000000), now=10)
        for changes in ({"attempt": 2}, {"run": "new-run"}):
            view = monitor.sample(reading(sampled_at=11, **changes), now=11)
            self.assertIsNone(view.audio_mbps)
            self.assertIsNone(view.resend_pps)

    def test_stale_and_stopped_measurements_do_not_report_live_rates(self):
        monitor = TrafficMonitor()
        monitor.sample(reading(), now=10)
        stale = monitor.sample(reading(audio_bytes=355000), now=14)
        self.assertEqual(stale.state, "Pomiar nieaktualny")
        self.assertIsNone(stale.audio_mbps)
        self.assertIsNone(stale.buffered_ms)
        stopped = monitor.sample(reading(state="stopped"), now=15)
        self.assertEqual(stopped.state, "Zatrzymana")
        self.assertIsNone(stopped.audio_pps)
        self.assertIsNone(stopped.max_gap_ms)

    def test_counter_reset_and_zero_elapsed_time_cannot_produce_negative_rates(self):
        monitor = TrafficMonitor()
        monitor.sample(reading(audio_bytes=1000, audio_packets=2), now=10)
        reset = monitor.sample(reading(sampled_at=11), now=11)
        self.assertIsNone(reset.audio_mbps)
        repeated = monitor.sample(reading(sampled_at=11), now=11)
        self.assertIsNone(repeated.audio_mbps)
        quiet = monitor.sample(reading(sampled_at=12), now=12)
        self.assertEqual(quiet.audio_mbps, 0)
        self.assertEqual(quiet.audio_pps, 0)
