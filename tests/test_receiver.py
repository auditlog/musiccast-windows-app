import io
import json
import unittest

from musiccast_bridge.demo import DemoTransport, demo_receiver
from musiccast_bridge.models import Capabilities, ReceiverStatus, VolumeRange
from musiccast_bridge.receiver import HttpTransport, ReceiverError, YamahaReceiver, validate_host


class RecordingTransport(DemoTransport):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        return await super().get(path, params)


class ModelsTests(unittest.TestCase):
    def test_volume_scale_is_not_assumed_to_be_100(self):
        bounds = VolumeRange(20, 180, 2)
        self.assertEqual(bounds.from_percent(50), 100)
        self.assertEqual(bounds.to_percent(100), 50)
        self.assertEqual(bounds.from_percent(100, ceiling=123), 122)

    def test_volume_rounds_on_receiver_step(self):
        self.assertEqual(VolumeRange(0, 161).normalize(100, ceiling=61), 61)
        self.assertEqual(VolumeRange(10, 50, 4).normalize(15), 14)
        self.assertEqual(VolumeRange(10, 50, 4).normalize(50, ceiling=35), 34)
        with self.assertRaises(ValueError):
            VolumeRange(0, 100).from_percent(-1)

    def test_invalid_capabilities_cannot_enable_controls(self):
        with self.assertRaises(ValueError):
            Capabilities.parse({"zone": [{"id": "zone2"}]})
        with self.assertRaises(ValueError):
            VolumeRange(100, 0)

    def test_display_volume_comes_from_api(self):
        status = ReceiverStatus.parse({"actual_volume": {"value": -42.5, "unit": "dB"}})
        self.assertEqual(status.volume_display, "-42.5 dB")
        self.assertIsNone(status.volume)

    def test_host_validation_prevents_url_injection(self):
        for value in [
            "",
            "http://192.168.1.1",
            "device:80",
            "x/a",
            "x@host",
            "x?foo=bar",
            "999.999.1.1",
            "239.255.255.250",
            "0.0.0.0",
            "foo\nbar",
        ]:
            with self.subTest(host=value), self.assertRaises(ValueError):
                validate_host(value)
        self.assertEqual(validate_host(" YAMAHA.local. "), "yamaha.local")
        self.assertEqual(validate_host("192.168.1.5"), "192.168.1.5")


class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = RecordingTransport()
        self.receiver = YamahaReceiver("192.168.1.50", self.transport)
        await self.receiver.connect()

    async def test_connect_only_reads(self):
        self.assertTrue(all("/get" in path for path, _ in self.transport.calls))

    async def test_volume_respects_live_max_volume(self):
        self.transport.status["max_volume"] = 51
        result = await self.receiver.set_volume(100)
        self.assertEqual(result.status.volume, 51)
        self.assertIn(("main/setVolume", {"volume": 51}), self.transport.calls)

    async def test_volume_steps_use_native_unit(self):
        self.transport.status["volume"] = 1
        result = await self.receiver.step_volume(1)
        self.assertEqual(result.status.volume, 2)
        result = await self.receiver.step_volume(-1)
        self.assertEqual(result.status.volume, 1)

    async def test_disabled_volume_does_not_send_command(self):
        self.transport.status["disable_flags"] = 1
        with self.assertRaises(ReceiverError):
            await self.receiver.set_volume(50)
        self.assertFalse(any(path == "main/setVolume" for path, _ in self.transport.calls))

    async def test_unknown_input_not_sent(self):
        with self.assertRaises(ReceiverError):
            await self.receiver.set_input("hdmi99")
        self.assertFalse(any(path == "main/setInput" for path, _ in self.transport.calls))

    async def test_playback_requires_source_attribute(self):
        await self.receiver.set_input("cd")
        with self.assertRaises(ReceiverError):
            await self.receiver.playback("pause")
        self.assertFalse(any(path == "netusb/setPlayback" for path, _ in self.transport.calls))

    async def test_source_selection_preserves_volume_and_mute(self):
        self.transport.status.update(volume=60, mute=True)
        await self.receiver.set_input("airplay")
        self.assertEqual(self.transport.status["volume"], 60)
        self.assertTrue(self.transport.status["mute"])
        self.assertFalse(any(path == "main/setVolume" for path, _ in self.transport.calls))

    async def test_demo_cannot_contact_network(self):
        demo = demo_receiver()
        snapshot = await demo.connect()
        self.assertTrue(snapshot.demo)
        snapshot = await demo.set_power("standby")
        self.assertEqual(snapshot.status.power, "standby")


class FakeResponse(io.BytesIO):
    pass


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.urls = []

    def open(self, url, timeout):
        self.urls.append(url)
        return FakeResponse(self.data)


class HttpTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_transport_encodes_boolean_and_path(self):
        transport = HttpTransport("yamaha.local")
        transport.opener = FakeOpener(b'{"response_code":0}')
        await transport.get("main/setMute", {"enable": True})
        self.assertEqual(
            transport.opener.urls,
            ["http://yamaha.local/YamahaExtendedControl/v1/main/setMute?enable=true"],
        )

    async def test_errors_are_checked_not_treated_as_success(self):
        for body in [
            b"not json",
            b"[]",
            b"{}",
            b'{"response_code":"0"}',
            b'{"response_code":false}',
            b'{"response_code":5}',
        ]:
            transport = HttpTransport("yamaha.local")
            transport.opener = FakeOpener(body)
            with self.subTest(body=body), self.assertRaises(ReceiverError):
                await transport.get("main/getStatus")

    async def test_set_command_is_not_retried(self):
        transport = HttpTransport("yamaha.local")
        transport.opener = FakeOpener(json.dumps({"response_code": 5}).encode())
        with self.assertRaises(ReceiverError):
            await transport.get("main/setPower", {"power": "on"})
        self.assertEqual(len(transport.opener.urls), 1)


if __name__ == "__main__":
    unittest.main()
