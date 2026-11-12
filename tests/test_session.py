import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from musiccast_bridge.audio import AudioError, PCMStream
from musiccast_bridge.session import Session
from musiccast_bridge.settings import Settings


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_optional_windows_route_is_prepared_before_capture_and_restored_on_stop(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        session.output_route.begin = AsyncMock()
        session.output_route.restore = AsyncMock()
        session.audio.start = AsyncMock()
        with patch("musiccast_bridge.session._pyaudio"):
            await session.start_audio(device_index=123, route_output_id="cable-id")
        session.output_route.begin.assert_awaited_once_with("cable-id")
        self.assertIsNone(session.audio.start.await_args.args[1])
        self.assertEqual(session.audio.start.await_args.kwargs["on_finished"],
                         session.output_route.restore)
        await session.stop_audio()
        session.output_route.restore.assert_awaited_once()

    async def test_windows_route_is_restored_when_capture_start_fails(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        session.output_route.begin = AsyncMock()
        session.output_route.restore = AsyncMock()
        session.audio.start = AsyncMock(side_effect=AudioError("capture failed"))
        with patch("musiccast_bridge.session._pyaudio"):
            with self.assertRaises(AudioError):
                await session.start_audio(route_output_id="cable-id")
        session.output_route.restore.assert_awaited_once()

    async def test_demonstration_can_never_start_real_stream(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        with self.assertRaisesRegex(AudioError, "demonstracyjny"):
            await session.start_audio()
        self.assertFalse(session.audio.active)

    async def test_stream_is_stopped_before_power_or_input_change(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        events = []
        session.audio.stop = AsyncMock(side_effect=lambda: events.append("stop"))
        original = session.receiver.set_power

        async def power(value):
            events.append("power")
            return await original(value)

        session.receiver.set_power = power
        await session.command("set_power", "standby")
        self.assertEqual(events, ["stop", "power"])

    async def test_bad_platform_fails_before_waking_receiver(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        await session.receiver.set_power("standby")
        with patch("musiccast_bridge.session._pyaudio", side_effect=AudioError("Windows wymagany")):
            with self.assertRaises(AudioError):
                await session.start_audio()
        self.assertEqual((await session.refresh()).status.power, "standby")

    async def test_mutations_are_serialized(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        await asyncio.gather(
            session.command("set_volume", 20),
            session.command("set_volume", 30),
            session.command("set_volume", 40),
        )
        self.assertEqual((await session.refresh()).status.volume, 64)

    async def test_shutdown_cancels_pending_restore_without_deadlock(self):
        session = Session()
        await session.connect("demo.local", demo=True)

        async def waiting_restore():
            async with session.lock:
                await asyncio.sleep(100)

        session.audio._task = asyncio.create_task(waiting_restore())
        async with asyncio.timeout(0.5):
            await session.close()
        self.assertFalse(session.audio.active)

    async def test_stop_during_preflight_prevents_late_wakeup(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        await session.receiver.set_power("standby")
        entered = asyncio.Event()

        async def suspended_refresh():
            entered.set()
            await asyncio.Event().wait()

        session.receiver.refresh = suspended_refresh
        start = asyncio.create_task(session.start_audio(filename="test.wav"))
        await entered.wait()
        async with asyncio.timeout(0.5):
            await session.stop_audio()
        self.assertTrue(start.cancelled())
        self.assertEqual(session.receiver.transport.status["power"], "standby")

    async def test_volume_control_cannot_release_audio_before_startup_confirmation(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.audio._task = asyncio.create_task(asyncio.Event().wait())
        source = PCMStream(44100, 2, gated=True)
        session.audio._source = source
        await session.command("set_volume", 0)
        self.assertFalse(source.enabled)
        await session.command("set_volume", 10)
        self.assertFalse(source.enabled)
        self.assertEqual(session.receiver.transport.status["volume"], 16)
        await session.close()

    async def test_start_wakes_receiver_selects_airplay_and_keeps_its_volume(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        receiver = session.receiver
        receiver.demo = False
        receiver.transport.status.update(power="standby", input="bluetooth", volume=0, mute=True)
        original = receiver.transport.get
        commands = []
        waking_polls = 0

        async def get(path, params=None):
            nonlocal waking_polls
            if path == "main/getStatus" and waking_polls:
                waking_polls -= 1
                if not waking_polls:
                    receiver.transport.status.update(power="on", volume=47)
            result = await original(path, params)
            if path.startswith("main/set"):
                commands.append(path)
            if path == "main/setPower":
                receiver.transport.status["power"] = "standby"
                waking_polls = 3  # Power and the receiver's start volume settle later.
            return result

        receiver.transport.get = get
        session.audio.start = AsyncMock()
        with patch("musiccast_bridge.session._STATUS_POLL_INTERVAL", 0.001):
            snapshot = await session.start_audio(filename="test.wav")
        self.assertEqual(snapshot.status.input, "airplay")
        self.assertEqual(snapshot.status.volume, 47)
        self.assertTrue(snapshot.status.mute)
        confirm = session.audio.start.await_args.kwargs["on_ready"]
        await confirm()
        self.assertEqual(commands, ["main/setPower", "main/setInput"])
        self.assertEqual(receiver.transport.status["volume"], 47)
        self.assertTrue(receiver.transport.status["mute"])

    async def test_source_is_rechecked_when_airplay_handshake_finishes(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        receiver = session.receiver
        receiver.demo = False
        receiver.transport.status.update(input="bluetooth", volume=55)
        session.audio.start = AsyncMock()
        await session.start_audio(filename="test.wav")
        receiver.transport.status["input"] = "bluetooth"  # Changed during RTSP setup.
        confirm = session.audio.start.await_args.kwargs["on_ready"]
        await confirm()
        self.assertEqual(receiver.transport.status["input"], "airplay")
        self.assertEqual(receiver.transport.status["volume"], 55)
        receiver.transport.status["power"] = "standby"
        with self.assertRaisesRegex(AudioError, "wyłączona"):
            await confirm()
        self.assertEqual(receiver.transport.status["power"], "standby")

    async def test_start_aborts_when_receiver_does_not_select_airplay(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        session.receiver.transport.status["input"] = "bluetooth"
        original = session.receiver.transport.get

        async def get(path, params=None):
            if path == "main/setInput":
                return {"response_code": 0}
            return await original(path, params)

        session.receiver.transport.get = get
        session.audio.start = AsyncMock()
        with patch("musiccast_bridge.session._STARTUP_TIMEOUT", 0.04), patch(
            "musiccast_bridge.session._STATUS_POLL_INTERVAL", 0.001
        ):
            with self.assertRaisesRegex(AudioError, "gotowości"):
                await session.start_audio(filename="test.wav")
        session.audio.start.assert_not_awaited()

    async def test_explicit_start_volume_applies_once_before_audio_is_released(self):
        session = Session()
        await session.connect("demo.local", demo=True)
        session.receiver.demo = False
        session.audio.start = AsyncMock()
        await session.start_audio(filename="test.wav", volume=5)
        confirm = session.audio.start.await_args.kwargs["on_ready"]
        await confirm()
        expected = session.receiver.capabilities.volume.from_percent(5)
        self.assertEqual(session.receiver.transport.status["volume"], expected)
        await session.command("set_volume", 20)
        chosen = session.receiver.transport.status["volume"]
        await confirm()  # A recovered connection uses the latest receiver volume.
        self.assertEqual(session.receiver.transport.status["volume"], chosen)


class SettingsTests(unittest.TestCase):
    def test_audio_device_name_survives_restart_without_saving_transient_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            name = "CABLE Input (VB-Audio Virtual Cable) [Loopback]"
            Settings(audio_device_name=name).save(path)
            self.assertEqual(Settings.load(path).audio_device_name, name)
            path.write_text('{"audio_device_name":23}', encoding="utf-8")
            self.assertEqual(Settings.load(path).audio_device_name, "")

    def test_roundtrip_and_corrupt_file_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            Settings("yamaha.local", False).save(path)
            settings = Settings.load(path)
            self.assertEqual(settings.host, "yamaha.local")
            self.assertFalse(settings.close_to_tray)
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual(Settings.load(path).host, "")


if __name__ == "__main__":
    unittest.main()
