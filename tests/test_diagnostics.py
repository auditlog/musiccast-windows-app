import asyncio
import json
import struct
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from musiccast_bridge.diagnostics import AirPlayDiagnostics
from musiccast_bridge.raop import configure_airplay


class DiagnosticTests(unittest.TestCase):
    def test_live_snapshot_is_a_copy_and_resets_between_runs_and_attempts(self):
        trace = AirPlayDiagnostics()
        trace.start("127.0.0.1", "windows")
        trace.attempt(1, "standard")
        trace.count("audio_bytes", 1000)
        trace.publish(buffered_ms=120, password="secret", headers={"secret": 1})
        trace.emit("sender_ready")
        snapshot = trace.snapshot()
        self.assertEqual(snapshot["state"], "playing")
        self.assertEqual(snapshot["buffered_ms"], 120)
        self.assertNotIn("secret", str(snapshot))
        snapshot["audio_bytes"] = 0
        self.assertEqual(trace.snapshot()["audio_bytes"], 1000)
        trace.attempt(2, "minimal")
        self.assertEqual(trace.snapshot()["state"], "connecting")
        self.assertEqual(trace.snapshot()["audio_bytes"], 0)
        self.assertNotIn("buffered_ms", trace.snapshot())
        trace.emit("session_stopped")
        self.assertEqual(trace.snapshot()["state"], "stopped")
        trace.start("127.0.0.1", "windows")
        self.assertNotEqual(snapshot["run"], trace.snapshot()["run"])
        self.assertNotIn("audio_bytes", trace.snapshot())

    def test_report_is_bounded_and_excludes_unapproved_fields(self):
        trace = AirPlayDiagnostics()
        trace.start("127.0.0.1", "windows")
        for index in range(600):
            trace.emit(
                "request",
                cseq=index,
                headers={"Authorization": "secret"},
                password="secret-password",
                body=b"captured audio",
                credentials="pairing secret",
            )
        rows = [json.loads(line) for line in trace.report().splitlines()]
        self.assertEqual(len(rows), 500)
        self.assertEqual(rows[-1]["cseq"], 599)
        self.assertNotIn("secret", trace.report())
        self.assertNotIn("captured audio", trace.report())


class ProtocolDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.utils = ModuleType("pyatv.protocols.airplay.utils")
        self.utils.AirPlayMajorVersion = SimpleNamespace(AirPlayV1=1)
        self.utils.get_protocol_version = lambda service, preferred: preferred
        errors = ModuleType("pyatv.exceptions")
        errors.ConnectionLostError = type("ConnectionLostError", (Exception,), {})
        packets = ModuleType("pyatv.protocols.raop.packets")
        packets.TimingPacket = SimpleNamespace(
            encode=lambda *fields: struct.pack("!BBH7I", *fields)
        )
        timing = ModuleType("pyatv.protocols.raop.timing")
        timing.ntp_now = lambda: (3_999_999_999 << 32) | 123456
        timing.ntp2parts = lambda value: (value >> 32, value & 0xFFFFFFFF)
        self.enterContext(
            patch.dict(
                "sys.modules",
                {
                    self.utils.__name__: self.utils,
                    errors.__name__: errors,
                    packets.__name__: packets,
                    timing.__name__: timing,
                },
            )
        )
        self.trace = AirPlayDiagnostics()
        self.trace.start("127.0.0.2", "windows")
        self.trace.attempt(1, "minimal")
        self.requests = []
        self.context = SimpleNamespace(
            rtsp_session=19,
            rtpseq=42,
            rtptime=66150,
            server_port=7001,
            control_port=9001,
            timing_port=9000,
            sample_rate=44100,
            channels=2,
            bytes_per_channel=2,
        )
        self.rtsp = SimpleNamespace(
            connection=SimpleNamespace(local_ip="127.0.0.1", remote_ip="127.0.0.2"), cseq=0
        )

        async def exchange(method, *args, **kwargs):
            self.requests.append((method, args, kwargs))
            self.rtsp.cseq += 1
            if method == "TEARDOWN":
                raise TimeoutError("no response to TEARDOWN")
            return SimpleNamespace(code=200)

        async def record(headers=None, body=None):
            return await self.rtsp.exchange("RECORD", headers=headers, body=body)

        async def teardown(session):
            return await self.rtsp.exchange("TEARDOWN", headers={"Session": session})

        async def parameter(name, value):
            return await self.rtsp.exchange("SET_PARAMETER", body=f"{name}: {value}")

        async def noop(*args, **kwargs):
            pass

        async def packet(*args, **kwargs):
            return 42, b"synthetic audio payload"

        self.rtsp.exchange = exchange
        self.rtsp.record = record
        self.rtsp.teardown = teardown
        self.rtsp.set_parameter = parameter
        self.protocol = SimpleNamespace(setup=noop, send_audio_packet=packet)
        self.udp_sent = []
        self.client = SimpleNamespace(
            rtsp=self.rtsp,
            _protocol=self.protocol,
            timing_server=SimpleNamespace(
                port=6001,
                datagram_received=lambda data, address: None,
                error_received=lambda error: None,
                transport=SimpleNamespace(
                    sendto=lambda data, address: self.udp_sent.append((data, address))
                ),
            ),
            control_client=SimpleNamespace(
                port=6002,
                datagram_received=lambda data, address: None,
                error_received=lambda error: None,
            ),
        )

        async def setup(service):
            return self.client, self.context

        self.manager = SimpleNamespace(setup=setup)
        self.service = SimpleNamespace(password="secret-password", credentials="pairing secret")
        self.settings = SimpleNamespace(protocol_version=1)
        raop = SimpleNamespace(
            core=SimpleNamespace(
                service=self.service,
                settings=SimpleNamespace(protocols=SimpleNamespace(raop=self.settings)),
            ),
            playback_manager=self.manager,
        )
        self.facade = SimpleNamespace(get=lambda protocol: raop)

    async def test_minimal_start_traces_rtsp_and_udp_without_payloads(self):
        ready = configure_airplay(self.facade, "raop", self.trace, minimal=True)
        await self.manager.setup(self.service)
        await self.rtsp.info()
        await self.protocol.setup(6001, 6002)
        await self.protocol.start_feedback()
        await self.rtsp.set_metadata("private title")
        await self.rtsp.set_parameter("progress", "0/0/0")
        await self.rtsp.set_parameter("volume", "-144")
        self.assertFalse(ready.is_set())
        await self.rtsp.record()
        self.assertTrue(ready.is_set())
        self.client.timing_server.datagram_received(b"timing", ("127.0.0.2", 9000))
        self.client.control_client.datagram_received(b"control", ("127.0.0.2", 9001))
        transport = SimpleNamespace(is_closing=lambda: False)
        await self.protocol.send_audio_packet(transport, b"header", b"pcm")
        self.assertEqual([request[0] for request in self.requests], ["RECORD"])
        self.assertEqual(self.requests[0][2]["headers"]["RTP-Info"], "seq=42;rtptime=66150")
        self.assertIn("volume_managed_by_receiver", self.trace.report())
        counters = self.trace.counters()
        self.assertEqual(counters["timing_requests"], 1)
        self.assertEqual(counters["timing_replies"], 1)
        self.assertEqual(counters["control_packets"], 1)
        self.assertEqual(counters["audio_packets"], 1)
        self.assertIn("rtsp_response", self.trace.report())
        for secret in (
            "secret-password",
            "pairing secret",
            "private title",
            "synthetic audio payload",
        ):
            self.assertNotIn(secret, self.trace.report())
        self.trace.failure_operation = "RECORD session"
        await asyncio.wait_for(self.rtsp.teardown(19), 1)
        self.assertIn("teardown_unconfirmed", self.trace.report())
        self.assertEqual(self.trace.failure_operation, "RECORD session")

    async def test_airplay_v2_records_without_legacy_headers_or_volume_write(self):
        self.settings.protocol_version = 2
        ready = configure_airplay(self.facade, "raop", self.trace, minimal=True)
        await self.manager.setup(self.service)
        self.assertFalse(ready.is_set())
        await self.rtsp.set_parameter("volume", "-144")
        await self.rtsp.record()
        self.assertTrue(ready.is_set())
        self.assertEqual([request[0] for request in self.requests], ["RECORD"])
        self.assertIsNone(self.requests[0][2]["headers"])
        self.assertFalse(hasattr(self.rtsp, "info"))

    async def test_standard_profile_suppresses_default_volume_before_and_after_record(self):
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        await self.rtsp.set_parameter("volume", "-144")
        await self.rtsp.record()
        await self.rtsp.set_parameter("volume", "-20.1")
        await self.rtsp.set_parameter("volume", "0")
        await self.rtsp.set_parameter("progress", "0/0/0")
        self.assertEqual([request[0] for request in self.requests], ["RECORD", "SET_PARAMETER"])
        self.assertEqual(self.requests[1][2]["body"], "progress: 0/0/0")

    async def test_retransmission_metrics_preserve_the_control_handler(self):
        received = []

        def receive(data, peer):
            received.append((data, peer))

        self.client.control_client.datagram_received = receive
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        await self.protocol.setup(6001, 6002)
        request = struct.pack("!BBHHH", 0x80, 0xD5, 7, 65534, 4)
        peer = ("127.0.0.2", 9001)
        self.client.control_client.datagram_received(request, peer)
        self.assertEqual(received, [(request, peer)])
        self.assertEqual(self.trace.counters()["retransmit_requests"], 1)
        self.assertEqual(self.trace.counters()["requested_packets"], 4)
        report = self.trace.report()
        self.assertIn('"sample_bits": 16', report)
        self.assertIn('"rate": 44100', report)
        self.assertIn("first_retransmission_request", report)

    async def test_resends_original_bytes_across_sequence_wrap_and_counts_missing(self):
        listener = self.client.control_client
        packets = {
            seq: struct.pack("!BBHII", 0x80, 0x60, seq, 12345, 7) + b"audio"
            for seq in (65534, 65535, 0, 42)
        }
        listener.packet_backlog = packets
        sent = []
        listener.transport = SimpleNamespace(
            sendto=lambda packet, peer: sent.append((packet, peer))
        )
        listener._retransmit_lost_packets = lambda request, peer: self.fail("old handler called")

        def receive(data, peer):
            start, count = struct.unpack_from("!HH", data, 4)
            listener._retransmit_lost_packets(
                SimpleNamespace(lost_seqno=start, lost_packets=count), peer
            )

        listener.datagram_received = receive
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        await self.protocol.setup(6001, 6002)
        peer = ("127.0.0.2", 9001)
        request = struct.pack("!BBHHH", 0x80, 0xD5, 7, 65534, 4)
        listener.datagram_received(request, peer)
        self.assertEqual(
            sent,
            [(b"\x80\xd6" + packets[seq][2:4] + packets[seq], peer) for seq in (65534, 65535, 0)],
        )
        self.assertEqual(self.trace.counters()["retransmitted_packets"], 3)
        self.assertEqual(
            self.trace.counters()["retransmitted_bytes"],
            sum(4 + len(packets[seq]) for seq in (65534, 65535, 0)),
        )
        self.assertEqual(self.trace.counters()["retransmit_unavailable"], 1)
        self.assertEqual(self.trace.counters()["requested_packets"], 4)
        self.assertEqual(self.trace.counters()["max_retransmit_age_packets"], 44)
        listener.datagram_received(request, ("127.0.0.3", 9001))
        listener.datagram_received(request[:6], peer)
        self.assertEqual(len(sent), 3)
        self.assertEqual(self.trace.counters()["ignored_udp_packets"], 2)

        # A very large request inspects only the bounded backlog, with no amplification
        # beyond actual stored packets. A send error is not counted as a resend.
        def blocked(packet, peer):
            raise OSError("unreachable")

        listener.transport.sendto = blocked
        listener.datagram_received(struct.pack("!BBHHH", 0x80, 0xD5, 7, 65534, 65535), peer)
        counters = self.trace.counters()
        self.assertEqual(counters["retransmitted_packets"], 3)
        self.assertEqual(counters["retransmit_send_errors"], 4)
        self.assertEqual(counters["retransmit_unavailable"], 1 + 65535 - 4)

    async def test_larger_retransmit_fifo_is_shared_by_sender_and_control_listener(self):
        module = ModuleType("pyatv.protocols.raop.fifo")

        class Fifo(dict):
            def __init__(self, limit):
                super().__init__()
                self.limit = limit

        module.PacketFifo = Fifo
        self.enterContext(patch.dict("sys.modules", {module.__name__: module}))
        self.client._packet_backlog = Fifo(1000)
        listener = self.client.control_client
        listener.packet_backlog = self.client._packet_backlog
        sent = []
        listener.transport = SimpleNamespace(sendto=lambda *args: sent.append(args))
        listener._retransmit_lost_packets = lambda *args: None
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        await self.protocol.setup(6001, 6002)
        self.assertEqual(self.client._packet_backlog.limit, 4096)
        self.assertIs(listener.packet_backlog, self.client._packet_backlog)
        # A requested packet 1500 packets behind would be absent from the old FIFO.
        for sequence in range(1600):
            self.client._packet_backlog[sequence] = struct.pack("!BBH", 0x80, 0x60, sequence)
        listener._retransmit_lost_packets(
            SimpleNamespace(lost_seqno=99, lost_packets=1), ("127.0.0.2", 9001)
        )
        self.assertEqual(self.trace.counters()["retransmitted_packets"], 1)
        self.assertEqual(self.trace.counters()["max_retransmit_age_packets"], 1500)
        self.assertEqual(len(sent), 1)

    async def test_send_gap_measurement_does_not_change_packet_data(self):
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        transport = SimpleNamespace(is_closing=lambda: False)
        with patch("musiccast_bridge.raop.time.monotonic", side_effect=[10, 10.1]):
            result = await self.protocol.send_audio_packet(transport, b"header", b"pcm")
            await self.protocol.send_audio_packet(transport, b"header", b"pcm")
        self.assertEqual(result, (42, b"synthetic audio payload"))
        self.assertEqual(self.trace.counters()["max_send_gap_ms"], 100)
        self.assertEqual(self.trace.counters()["send_gaps_over_50ms"], 1)

    async def test_timing_probe_precedes_record_and_allows_return_traffic(self):
        original_record = self.rtsp.record

        async def record_requiring_timing(headers=None, body=None):
            if not self.trace.counters().get("timing_requests"):
                raise TimeoutError("no response to RECORD")
            return await original_record(headers=headers, body=body)

        def sendto(data, address):
            self.udp_sent.append((data, address))
            self.client.timing_server.datagram_received(b"incoming timing", address)

        self.rtsp.record = record_requiring_timing
        self.client.timing_server.transport.sendto = sendto
        ready = configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        await self.protocol.setup(6001, 6002)
        self.assertEqual(len(self.udp_sent), 1)
        data, address = self.udp_sent[0]
        self.assertEqual(address, ("127.0.0.2", 9000))
        self.assertEqual(len(data), 32)
        fields = struct.unpack("!BBH7I", data)
        self.assertEqual(fields[:4], (0x80, 0xD3, 7, 0))
        self.assertEqual(fields[4:], (3_999_999_999, 123456) * 3)
        await self.rtsp.record()
        self.assertTrue(ready.is_set())
        report = self.trace.report()
        self.assertIn("timing_probe_sent", report)
        self.assertIn("first_timing_request", report)

    async def test_timing_probe_skips_absent_port_and_reports_send_failure(self):
        configure_airplay(self.facade, "raop", self.trace)
        await self.manager.setup(self.service)
        self.context.timing_port = 0
        await self.protocol.setup(6001, 6002)
        self.assertEqual(self.udp_sent, [])
        self.assertIn("timing_probe_skipped", self.trace.report())
        self.context.timing_port = 9000

        def blocked(*args):
            raise PermissionError(13, "denied")

        self.client.timing_server.transport.sendto = blocked
        with self.assertRaisesRegex(ConnectionError, "synchronizacji"):
            await self.protocol.setup(6001, 6002)
        self.assertIn("timing_probe_failed", self.trace.report())
