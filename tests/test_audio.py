import array
import asyncio
import io
import struct
import tempfile
import threading
import time
import unicodedata
import unittest
import wave
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from musiccast_bridge.audio import (
    AudioError,
    AudioStreamer,
    GatedFileStream,
    LoopbackCapture,
    PCMStream,
    create_test_tone,
)


class PCMTests(unittest.TestCase):
    def test_wav_header_and_pcm_are_valid(self):
        pipe = PCMStream(48000, 2)
        pcm = struct.pack("<hhhh", 100, -100, 200, -200)
        pipe.feed(pcm)
        stream = io.BytesIO(pipe.read(44 + len(pcm)))
        with wave.open(stream) as wav:
            self.assertEqual(wav.getframerate(), 48000)
            self.assertEqual(wav.getnchannels(), 2)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.readframes(2), pcm)

    def test_zero_size_read_does_not_consume_header(self):
        pipe = PCMStream(44100, 2)
        self.assertEqual(pipe.read(0), b"")
        self.assertEqual(pipe.read(4), b"RIFF")

    def test_backlog_bounded_and_drops_oldest_whole_frames(self):
        pipe = PCMStream(8000, 2, buffer_seconds=0.001)
        pipe.read(44)
        pipe.feed(bytes(range(32)))
        pipe.read(1)  # An arbitrary decoder read must not corrupt frame-drop alignment.
        pipe.feed(bytes(range(32, 64)))
        self.assertLessEqual(pipe.buffered_bytes, pipe.capacity)
        self.assertEqual(pipe.dropped_bytes % 4, 0)
        self.assertEqual(pipe.read(4), bytes(range(33, 37)))

    def test_finish_unblocks_a_reader(self):
        pipe = PCMStream(48000, 2)
        pipe.read(44)
        result = []
        reader = threading.Thread(target=lambda: result.append(pipe.read(192000)))
        reader.start()
        time.sleep(0.02)
        pipe.finish()
        reader.join(timeout=0.5)
        self.assertFalse(reader.is_alive())
        self.assertEqual(result, [b""])

    def test_silence_is_paced_instead_of_eof(self):
        pipe = PCMStream(8000, 1)
        pipe.read(44)
        start = time.monotonic()
        self.assertEqual(pipe.read(320), bytes(320))
        self.assertGreaterEqual(time.monotonic() - start, 0.015)

    def test_capture_errors_are_propagated_to_decoder(self):
        pipe = PCMStream(44100, 2)
        pipe.finish("Urządzenie odłączone")
        with self.assertRaisesRegex(AudioError, "odłączone"):
            pipe.read(100)

    def test_tone_is_short_quiet_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.wav"
            create_test_tone(path, duration=0.1)
            with wave.open(str(path)) as wav:
                self.assertEqual(wav.getnframes(), 4410)
                samples = struct.unpack("<" + "h" * 8820, wav.readframes(4410))
                self.assertLessEqual(max(abs(v) for v in samples), 900)

    def test_pcm_stays_silent_until_explicit_enable(self):
        pipe = PCMStream(44100, 2, gated=True)
        pipe.read(44)
        data = struct.pack("<hhhh", 100, -100, 200, -200)
        pipe.feed(data)
        self.assertEqual(pipe.read(8), bytes(8))
        pipe.enable()
        pipe.feed(data)
        pipe.enable()  # Subsequent volume changes must not discard buffered audio.
        self.assertEqual(pipe.read(8), data)

    def test_handshake_discards_capture_without_filling_the_live_backlog(self):
        pipe = PCMStream(44100, 2, gated=True)
        pipe.feed(bytes(pipe.capacity * 3))
        self.assertEqual(pipe.buffered_bytes, 0)
        self.assertEqual(pipe.dropped_bytes, 0)
        pipe.close()

    def test_underrun_counts_only_missing_live_samples(self):
        pipe = PCMStream(8000, 1, gated=True)
        pipe.read(44)
        pipe.read(8)
        self.assertEqual(pipe.inserted_silence_bytes, 0)
        pipe.enable()
        pipe.feed(b"\x01\x00" * 2)
        self.assertEqual(pipe.read(8), b"\x01\x00" * 2 + bytes(4))
        self.assertEqual(pipe.inserted_silence_bytes, 4)
        self.assertEqual(pipe.underflow_reads, 1)
        self.assertEqual(pipe.dropped_bytes, 0)
        pipe.close()

    def test_file_is_not_consumed_while_gate_is_closed(self):
        samples = array.array("h", [100, -100, 200, -200])
        stream = GatedFileStream("unused.wav", decoder=[samples])
        stream.read(44)
        self.assertEqual(stream.read(8), bytes(8))
        stream.enable()
        self.assertEqual(stream.read(8), samples.tobytes())
        self.assertEqual(stream.read(8), b"")

    def test_detached_device_still_releases_native_resources(self):
        events = []

        def stop():
            events.append("stop")
            raise OSError("device removed")

        capture = LoopbackCapture()
        capture._stream = SimpleNamespace(stop_stream=stop, close=lambda: events.append("close"))
        capture._manager = SimpleNamespace(terminate=lambda: events.append("terminate"))
        with self.assertLogs("musiccast_bridge.audio", level="WARNING"):
            capture.close()
        self.assertEqual(events, ["stop", "close", "terminate"])

    def test_stop_while_decoding_does_not_drain_file_or_close_active_generator(self):
        entered, release = threading.Event(), threading.Event()
        consumed, errors, output = [], [], []

        def decoder():
            for index in range(100):
                consumed.append(index)
                entered.set()
                release.wait(0.5)
                yield array.array("h", [100] * 4)

        stream = GatedFileStream("unused.wav", decoder=decoder())
        stream.enable()
        stream.read(44)

        def read():
            try:
                output.append(stream.read(64))
            except Exception as error:
                errors.append(error)

        def close():
            try:
                stream.close()
            except Exception as error:
                errors.append(error)

        reader = threading.Thread(target=read)
        reader.start()
        self.assertTrue(entered.wait(0.5))
        stream.finish()
        closer = threading.Thread(target=close)
        closer.start()
        release.set()
        reader.join(0.5)
        closer.join(0.5)
        self.assertFalse(reader.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(consumed, [0])
        self.assertEqual(errors, [])
        self.assertEqual(output, [b""])


class StreamingLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.enterContext(
            patch("musiccast_bridge.credentials.sys", SimpleNamespace(platform="test"))
        )
        self.events = []
        self.hold = asyncio.Event()
        self.module = ModuleType("pyatv")
        self.const = ModuleType("pyatv.const")
        self.interface = ModuleType("pyatv.interface")
        self.exceptions = ModuleType("pyatv.exceptions")
        self.exceptions.AuthenticationError = type("AuthenticationError", (Exception,), {})
        self.exceptions.PairingError = type("PairingError", (Exception,), {})
        self.exceptions.ProtocolError = type("ProtocolError", (Exception,), {})
        self.exceptions.ConnectionLostError = type("ConnectionLostError", (Exception,), {})
        self.exceptions.ConnectionFailedError = type("ConnectionFailedError", (Exception,), {})
        self.const.Protocol = SimpleNamespace(RAOP="raop")
        self.const.DeviceState = SimpleNamespace(Playing="playing")
        self.const.PairingRequirement = SimpleNamespace(
            Mandatory="mandatory",
            NotNeeded="not_needed",
            Disabled="disabled",
            Unsupported="unsupported",
        )
        self.interface.MediaMetadata = SimpleNamespace
        self.service = SimpleNamespace(
            identifier="receiver",
            port=7000,
            password=None,
            credentials=None,
            requires_password=False,
            pairing=self.const.PairingRequirement.NotNeeded,
        )
        self.config = SimpleNamespace(get_service=lambda protocol: self.service)

        async def scan(loop, timeout, hosts, protocol):  # noqa: ASYNC109 -- upstream API
            self.events.append("scan")
            return [self.config]

        async def set_volume(value):
            self.events.append(("volume", value))

        async def stream_file(source, metadata):
            self.events.append("send")
            self.source = source
            self.metadata = metadata
            # Models upstream's early local Playing and rejected initial volume,
            # before any actual RECORD acknowledgement. The PCM gate must stay shut.
            self.events.append("receiver_rejected_initial_volume")
            await self.hold.wait()

        async def playing():
            await asyncio.sleep(0)
            return SimpleNamespace(device_state="playing")

        def close():
            self.events.append("close")
            return set()

        async def connect(config, loop, protocol):
            self.events.append("connect")
            return SimpleNamespace(
                audio=SimpleNamespace(set_volume=set_volume),
                stream=SimpleNamespace(stream_file=stream_file),
                metadata=SimpleNamespace(playing=playing),
                close=close,
            )

        self.module.scan = scan
        self.module.connect = connect
        self.patch = patch.dict(
            "sys.modules",
            {
                "pyatv": self.module,
                "pyatv.const": self.const,
                "pyatv.interface": self.interface,
                "pyatv.exceptions": self.exceptions,
            },
        )
        self.patch.start()
        self.directory = tempfile.TemporaryDirectory()
        self.filename = Path(self.directory.name) / "tone.wav"
        create_test_tone(self.filename, 0.05)
        self.source_patch = patch(
            "musiccast_bridge.audio.GatedFileStream",
            side_effect=lambda path: GatedFileStream(
                path, decoder=[array.array("h", [100] * 2048)]
            ),
        )
        self.source_patch.start()

    async def asyncTearDown(self):
        self.patch.stop()
        self.source_patch.stop()
        self.directory.cleanup()

    async def test_audio_opens_after_receiver_confirmation_without_volume_write(self):
        notifications = []
        confirming = asyncio.Event()
        confirmed = asyncio.Event()

        def notify(state, text):
            notifications.append(state)

        async def on_ready():
            confirming.set()
            await confirmed.wait()

        sender = AudioStreamer(notify)

        await sender.start("127.0.0.1", filename=str(self.filename), on_ready=on_ready)
        async with asyncio.timeout(2):
            await confirming.wait()
        self.assertFalse(self.source.enabled)
        self.source.read(44)
        self.assertEqual(self.source.read(8), bytes(8))
        confirmed.set()
        await asyncio.wait_for(sender.wait_until_running(), 2)
        self.assertTrue(self.source.enabled)
        self.assertFalse(
            any(isinstance(event, tuple) and event[0] == "volume" for event in self.events)
        )
        self.assertTrue(sender.active)
        await sender.stop()
        self.assertFalse(sender.active)
        self.assertIn("close", self.events)
        self.assertEqual(notifications[-1], "stopped")

    async def test_stream_failure_is_reported_and_resources_closed(self):
        sender = AudioStreamer()
        finalized = []

        async def finished():
            finalized.append("restored")

        async def failed_scan(*args, **kwargs):
            raise AudioError("Brak odbiornika")

        self.module.scan = failed_scan
        await sender.start("127.0.0.1", filename=str(self.filename), on_finished=finished)
        async with asyncio.timeout(2):
            await sender.wait()
        self.assertIn("odbiornika", sender.last_error)
        self.assertEqual(finalized, ["restored"])
        await sender.stop()

    async def test_receiver_confirmation_failure_keeps_audio_closed(self):
        async def not_ready():
            raise AudioError("Yamaha nie potwierdziła wejścia AirPlay")

        sender = AudioStreamer()
        await sender.start("127.0.0.1", filename=str(self.filename), on_ready=not_ready)
        async with asyncio.timeout(2):
            await sender.wait()
        self.assertFalse(self.source.enabled)
        self.assertIn("nie potwierdziła", sender.last_error)
        self.assertNotIn("sender_ready", sender.diagnostics.report())
        self.assertIn("close", self.events)
        self.assertFalse(sender.active)
        await sender.stop()

    async def test_receiver_metadata_uses_plain_polish_letters(self):
        filename = self.filename.with_name(unicodedata.normalize("NFD", "Zażółć gęślą jaźń.wav"))
        self.filename.rename(filename)
        sender = AudioStreamer()
        try:
            await sender.start("127.0.0.1", filename=str(filename))
            await asyncio.wait_for(sender.wait_until_running(), 2)
            self.assertEqual(self.metadata.title, "Zazolc gesla jazn.wav")
        finally:
            await sender.stop()

    async def test_airplay_v1_sends_record_headers_and_waits_for_receiver(self):
        connect = self.module.connect
        sent = asyncio.Event()
        acknowledged = asyncio.Event()
        airplay = ModuleType("pyatv.protocols.airplay.utils")
        airplay.AirPlayMajorVersion = SimpleNamespace(AirPlayV1=1)
        airplay.get_protocol_version = lambda service, preferred: 1
        context = SimpleNamespace(rtsp_session=0, rtpseq=0, rtptime=0)

        async def record(headers=None, body=None):
            self.assertEqual(
                headers, {"Session": 19, "Range": "npt=0-", "RTP-Info": "seq=42;rtptime=66150"}
            )
            sent.set()
            await acknowledged.wait()

        async def noop(*args, **kwargs):
            return SimpleNamespace(code=200)

        client = SimpleNamespace(
            rtsp=SimpleNamespace(
                record=record, exchange=noop, teardown=noop,
                set_parameter=noop,
                connection=SimpleNamespace(local_ip="127.0.0.1", remote_ip="127.0.0.2"),
            ),
            _protocol=SimpleNamespace(setup=noop, send_audio_packet=noop),
        )

        async def setup(service):
            return client, context

        raop = SimpleNamespace(
            core=SimpleNamespace(
                service=self.service,
                settings=SimpleNamespace(
                    protocols=SimpleNamespace(raop=SimpleNamespace(protocol_version="auto"))
                ),
            ),
            playback_manager=SimpleNamespace(setup=setup),
        )

        async def stream_file(source, metadata):
            self.source = source
            await raop.playback_manager.setup(self.service)
            # Upstream sets these after the TCP connection has been opened.
            context.rtsp_session = 19
            context.rtpseq = 42
            context.rtptime = 66150
            await client.rtsp.record()
            await self.hold.wait()

        async def connect_with_legacy_receiver(config, loop, protocol):
            connection = await connect(config, loop, protocol)
            connection.stream.get = lambda protocol: raop
            connection.stream.stream_file = stream_file
            return connection

        self.module.connect = connect_with_legacy_receiver
        states = []
        sender = AudioStreamer(lambda state, text: states.append(state))
        with patch.dict("sys.modules", {airplay.__name__: airplay}):
            try:
                await sender.start("127.0.0.1", filename=str(self.filename))
                await asyncio.wait_for(sent.wait(), 2)
                self.assertNotIn("playing", states)
                self.assertFalse(self.source.enabled)
                acknowledged.set()
                await asyncio.wait_for(sender.wait_until_running(), 2)
                self.assertIn("playing", states)
                self.assertTrue(self.source.enabled)
            finally:
                await sender.stop()

    async def test_authentication_rejection_retries_with_password_on_new_connection(self):
        connect = self.module.connect
        passwords = []

        async def reject(*args, **kwargs):
            raise self.exceptions.AuthenticationError("not authenticated")

        async def idle():
            return SimpleNamespace(device_state="idle")

        async def connect_with_challenge(config, loop, protocol):
            passwords.append(config.get_service(protocol).password)
            connection = await connect(config, loop, protocol)
            if passwords[-1] is None:
                connection.stream.stream_file = reject
                connection.metadata.playing = idle
            return connection

        async def prompt(title, message):
            self.events.append("prompt")
            self.assertEqual(title, "Hasło AirPlay")
            return "example-password"

        self.module.connect = connect_with_challenge
        sender = AudioStreamer(request_secret=prompt)
        try:
            with self.assertLogs("musiccast_bridge.audio", level="WARNING") as logs:
                await sender.start("127.0.0.1", filename=str(self.filename))
                await asyncio.wait_for(sender.wait_until_running(), 2)
            self.assertEqual(passwords, [None, "example-password"])
            self.assertLess(self.events.index("close"), self.events.index("prompt"))
            self.assertNotIn("example-password", "\n".join(logs.output))
            self.assertTrue(self.source.enabled)
        finally:
            await sender.stop()

    async def test_record_timeout_retries_with_minimal_profile_and_new_source(self):
        sender = AudioStreamer()
        original_connect = self.module.connect
        attempts = []
        first_source = []

        async def idle():
            return SimpleNamespace(device_state="idle")

        async def fail_first(source, metadata):
            first_source.append(source)
            sender.diagnostics.airplay_version = 1
            sender.diagnostics.failure_operation = "RECORD session"
            raise TimeoutError("no response to RECORD")

        async def connect_with_timeout(config, loop, protocol):
            attempts.append(sender._minimal_start)
            connection = await original_connect(config, loop, protocol)
            if len(attempts) == 1:
                connection.stream.stream_file = fail_first
                connection.metadata.playing = idle
            return connection

        self.module.connect = connect_with_timeout
        with patch("musiccast_bridge.audio._RECOVERY_DELAYS", (0, 0)):
            try:
                await sender.start("127.0.0.1", filename=str(self.filename))
                await asyncio.wait_for(sender.wait_until_running(), 2)
                self.assertEqual(attempts, [False, True])
                self.assertIsNone(sender.last_error)
                self.assertTrue(self.source.enabled)
                self.assertTrue(first_source[0].closed)
                self.assertIsNot(self.source, first_source[0])
                self.assertIn("recovery_scheduled", sender.diagnostics.report())
            finally:
                await sender.stop()

    async def test_missing_packet_progress_is_detected(self):
        sender = AudioStreamer()
        sender.diagnostics.attempt(1, "standard")
        sender.diagnostics.instrumented = True
        sender._source = PCMStream(44100, 2, gated=True)
        task = asyncio.create_task(self.hold.wait())
        try:
            with patch("musiccast_bridge.audio._HEALTH_INTERVAL", 0.001):
                with self.assertRaisesRegex(TimeoutError, "pakiety"):
                    await asyncio.wait_for(sender._wait_for_stream(task), 1)
            self.assertIn("stream_stalled", sender.diagnostics.report())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            sender._source.close()

    async def test_recovery_is_bounded_and_stop_cancels_backoff(self):
        sender = AudioStreamer()
        failed = asyncio.Event()
        attempts = []

        async def fail(*args, **kwargs):
            attempts.append(True)
            failed.set()
            raise TimeoutError("no response to RECORD")

        with patch.object(sender, "_stream", side_effect=fail):
            with patch("musiccast_bridge.audio._RECOVERY_DELAYS", (60, 60)):
                await sender.start("127.0.0.1", filename=str(self.filename))
                await asyncio.wait_for(failed.wait(), 2)
                await asyncio.wait_for(sender.stop(), 2)
                self.assertEqual(len(attempts), 1)
                self.assertIsNone(sender.last_error)
            attempts.clear()
            with patch("musiccast_bridge.audio._RECOVERY_DELAYS", (0, 0)):
                with self.assertLogs("musiccast_bridge.audio", level="WARNING"):
                    await sender.start("127.0.0.1", filename=str(self.filename))
                    await asyncio.wait_for(sender.wait(), 2)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(
                sender.last_error,
                "Yamaha nie odpowiedziała na czas. Sprawdź połączenie i ponów próbę.",
            )
            self.assertIn("recovery_exhausted", sender.diagnostics.report())

    async def test_receiver_password_prompt_can_be_cancelled_before_connecting(self):
        self.service.requires_password = True
        prompted = asyncio.Event()

        async def prompt(title, message):
            prompted.set()
            return None

        sender = AudioStreamer(request_secret=prompt)
        await sender.start("127.0.0.1", filename=str(self.filename))
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(sender.wait(), 2)
        self.assertTrue(prompted.is_set())
        self.assertNotIn("connect", self.events)
        self.assertIsNone(sender.last_error)

    async def test_saved_password_rejected_then_replaced_and_reused(self):
        connect = self.module.connect
        passwords = []
        prompts = []
        self.service.requires_password = True

        async def reject(*args, **kwargs):
            raise self.exceptions.AuthenticationError("not authenticated")

        async def idle():
            return SimpleNamespace(device_state="idle")

        async def connect_with_password(config, loop, protocol):
            passwords.append(config.get_service(protocol).password)
            connection = await connect(config, loop, protocol)
            if passwords[-1] == "old-password":
                connection.stream.stream_file = reject
                connection.metadata.playing = idle
            return connection

        async def prompt(title, message):
            prompts.append(title)
            return "new-password"

        self.module.connect = connect_with_password
        sender = AudioStreamer(request_secret=prompt)
        sender._credentials.write(self.service.identifier, "password", "old-password")
        try:
            with self.assertLogs("musiccast_bridge.audio", level="WARNING"):
                for _ in range(2):
                    self.service.password = None
                    await sender.start("127.0.0.1", filename=str(self.filename))
                    await asyncio.wait_for(sender.wait_until_running(), 2)
                    await sender.stop()
            self.assertEqual(passwords, ["old-password", "new-password", "new-password"])
            self.assertEqual(prompts, ["Hasło AirPlay"])
        finally:
            await sender.stop()

    async def test_teardown_timeout_preserves_playback_failure(self):
        connect = self.module.connect

        async def teardown():
            # Match the nested timeout and cancellation used by pyatv's HTTP layer.
            try:
                async with asyncio.timeout(0):
                    await asyncio.Event().wait()
            except TimeoutError as error:
                raise TimeoutError("no response to TEARDOWN rtsp://receiver") from error

        async def send_audio(source, metadata):
            try:
                raise AudioError("Brak odpowiedzi na RECORD")
            finally:
                await teardown()

        async def connect_with_teardown_timeout(config, loop, protocol):
            connection = await connect(config, loop, protocol)
            connection.stream.stream_file = send_audio
            return connection

        self.module.connect = connect_with_teardown_timeout
        sender = AudioStreamer()
        with self.assertLogs("musiccast_bridge.audio", level="WARNING") as logs:
            await sender.start("127.0.0.1", filename=str(self.filename))
            await asyncio.wait_for(sender.wait(), 2)
        self.assertEqual(sender.last_error, "Brak odpowiedzi na RECORD")
        self.assertTrue(any("did not acknowledge TEARDOWN" in row for row in logs.output))
        self.assertIn("close", self.events)

    async def test_mandatory_pairing_is_used_again_in_the_same_app_session(self):
        self.service.pairing = self.const.PairingRequirement.Mandatory
        pairing = SimpleNamespace(has_paired=False, service=SimpleNamespace(credentials=None))

        async def begin():
            self.events.append("begin_pair")

        async def finish():
            pairing.has_paired = True
            pairing.service.credentials = "example-pairing-data"

        async def close():
            self.events.append("close_pair")

        pairing.begin, pairing.finish, pairing.close = begin, finish, close
        pairing.pin = lambda pin: self.events.append(("pin", pin))

        async def pair(config, protocol, loop, **kwargs):
            return pairing

        async def prompt(title, message):
            self.assertEqual(title, "Kod parowania AirPlay")
            return "0123"

        self.module.pair = pair
        sender = AudioStreamer(request_secret=prompt)
        try:
            for _ in range(2):
                self.service.credentials = None  # A new discovery config has no credentials.
                await sender.start("127.0.0.1", filename=str(self.filename))
                await asyncio.wait_for(sender.wait_until_running(), 2)
                self.assertEqual(self.service.credentials, "example-pairing-data")
                await sender.stop()
            self.assertEqual(self.events.count("begin_pair"), 1)
            self.assertEqual(self.events.count("close_pair"), 1)
            self.assertIn(("pin", 123), self.events)
        finally:
            await sender.stop()
