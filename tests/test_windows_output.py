import asyncio
import json
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from musiccast_bridge.windows_output import OutputError, OutputRoute, WindowsOutput


class FakeOutput:
    def __init__(self):
        self.state = {
            "devices": [{"id": x, "name": x} for x in ("speakers", "headphones", "cable")],
            "defaults": {"0": "speakers", "1": "headphones", "2": "communications"},
        }
        self.changes = []
        self.claimed = False

    def claim(self):
        self.claimed = True

    def release(self):
        self.claimed = False

    def query(self):
        return deepcopy(self.state)

    def select(self, endpoint, roles):
        self.changes.append((endpoint, list(roles)))
        for role in roles:
            self.state["defaults"][str(role)] = endpoint
        return self.query()


class OutputRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = FakeOutput()
        self.path = Path(self.temp.name) / "route.json"
        self.route = OutputRoute(self.backend, self.path)

    async def test_start_stop_restores_each_role_and_leaves_communications_untouched(self):
        previous = self.backend.query()
        await self.route.begin("cable")
        self.assertTrue(self.path.exists())
        self.assertEqual(self.backend.state["defaults"], {
            "0": "cable", "1": "cable", "2": "communications"})
        await self.route.restore()
        self.assertEqual(self.backend.query(), previous)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.backend.claimed)

    async def test_manual_change_of_one_role_is_preserved(self):
        await self.route.begin("cable")
        self.backend.state["defaults"]["1"] = "speakers"
        await self.route.restore()
        self.assertEqual(self.backend.state["defaults"]["1"], "speakers")
        self.assertEqual(self.backend.state["defaults"]["0"], "speakers")
        self.assertNotIn(("headphones", ["1"]), self.backend.changes)

    async def test_missing_target_does_not_change_output(self):
        with self.assertRaises(OutputError):
            await self.route.begin("absent")
        self.assertEqual(self.backend.changes, [])
        self.assertFalse(self.backend.claimed)

    async def test_partial_switch_failure_rolls_back_already_changed_role(self):
        real = self.backend.select

        def fail(endpoint, roles):
            if endpoint == "cable":
                real(endpoint, ["0"])
                raise OutputError("Partial change")
            return real(endpoint, roles)

        with patch.object(self.backend, "select", side_effect=fail):
            with self.assertRaisesRegex(OutputError, "Partial"):
                await self.route.begin("cable")
        self.assertEqual(self.backend.state["defaults"]["0"], "speakers")
        self.assertEqual(self.backend.state["defaults"]["1"], "headphones")
        self.assertFalse(self.path.exists())

    async def test_missing_original_keeps_journal_for_explicit_recovery(self):
        await self.route.begin("cable")
        self.backend.state["devices"] = [x for x in self.backend.state["devices"]
                                         if x["id"] != "headphones"]
        with self.assertRaises(OutputError):
            await self.route.restore()
        self.assertTrue(self.path.exists())
        self.backend.state["devices"].append({"id": "headphones", "name": "Headphones"})
        fresh = OutputRoute(self.backend, self.path)
        await fresh.restore(recover=True)
        self.assertEqual(self.backend.state["defaults"]["1"], "headphones")
        self.assertFalse(self.path.exists())

    async def test_restart_does_not_change_output_without_explicit_recovery(self):
        await self.route.begin("cable")
        fresh = OutputRoute(self.backend, self.path)
        await fresh.restore()
        self.assertEqual(self.backend.state["defaults"]["1"], "cable")
        await fresh.restore(recover=True)
        self.assertEqual(self.backend.state["defaults"]["1"], "headphones")

    async def test_corrupt_journal_never_changes_output(self):
        self.path.write_text(json.dumps({"target": "cable", "previous": {"2": "secret"}}))
        with self.assertRaises(OutputError):
            await self.route.restore(recover=True)
        self.assertEqual(self.backend.changes, [])
        self.assertTrue(self.path.exists())

    async def test_cancelled_start_waits_for_system_change_then_restores(self):
        entered, proceed = threading.Event(), threading.Event()
        select = self.backend.select

        def slow(endpoint, roles):
            if endpoint == "cable":
                entered.set()
                if not proceed.wait(2):
                    raise RuntimeError("test timed out")
            return select(endpoint, roles)

        with patch.object(self.backend, "select", side_effect=slow):
            task = asyncio.create_task(self.route.begin("cable"))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()  # Stop followed by quit must not cancel the native mutation wait.
            proceed.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(self.backend.state["defaults"]["1"], "headphones")
        self.assertFalse(self.path.exists())


@unittest.skipUnless(sys.platform == "win32", "Native Windows Core Audio check")
class NativeOutputTests(unittest.TestCase):
    def test_bundled_helper_compiles_and_reads_without_changing_defaults(self):
        state = WindowsOutput().query()
        self.assertIsInstance(state["devices"], list)
        for device in state["devices"]:
            self.assertTrue(device["id"])
            self.assertIsInstance(device["name"], str)


class HelperTransportTests(unittest.TestCase):
    def test_collection_iid_matches_microsoft_windows_sdk(self):
        # Microsoft win32metadata, um/mmdeviceapi.h: IID_IMMDeviceCollection.
        # Regression for the real E_NOINTERFACE failure reported on Windows.
        script = Path(__file__).resolve().parents[1] / (
            "src/musiccast_bridge/windows_output.ps1")
        source = script.read_text(encoding="utf-8")
        self.assertIn('Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E")', source)
        self.assertNotIn("C0A1CFE4480B", source)

    def test_non_windows_refuses_without_launching_a_subprocess(self):
        with patch("musiccast_bridge.windows_output.sys.platform", "linux"), patch(
            "musiccast_bridge.windows_output.subprocess.run") as run:
            with self.assertRaises(OutputError):
                WindowsOutput().query()
            run.assert_not_called()
