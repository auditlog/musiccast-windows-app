"""Serialized receiver commands and an independently cancellable audio session."""

import asyncio

from .audio import AudioError, AudioStreamer, _pyaudio
from .demo import demo_receiver
from .i18n import tr
from .receiver import ReceiverError, YamahaReceiver
from .windows_output import OutputRoute

_STARTUP_TIMEOUT = 10
_STATUS_POLL_INTERVAL = 0.25


class Session:
    def __init__(self, notify=None, request_secret=None):
        self.receiver: YamahaReceiver | None = None
        self.audio = AudioStreamer(notify, request_secret)
        self.lock = asyncio.Lock()
        self._preparing: asyncio.Task | None = None
        self._observed_state = None
        self.output_route = OutputRoute()

    async def _cancel_preparation(self):
        task = self._preparing
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def connect(self, host: str, demo: bool = False):
        await self._cancel_preparation()
        async with self.lock:
            await self.audio.stop()
            await self.output_route.restore()
            # Discard stale state even if attaching the new device fails.
            self.receiver = None
            receiver = demo_receiver() if demo else YamahaReceiver(host)
            snapshot = await receiver.connect()
            self.receiver = receiver
            return snapshot

    async def refresh(self):
        async with self.lock:
            snapshot = await self._receiver().refresh()
            state = snapshot.status
            observed = (state.power, state.input, state.mute, state.volume)
            if self.audio.active and observed != self._observed_state:
                self.audio.diagnostics.emit(
                    "receiver_state",
                    power=state.power,
                    input=state.input,
                    mute=state.mute,
                    volume=state.volume,
                )
                self._observed_state = observed
            return snapshot

    def _receiver(self):
        if self.receiver is None:
            raise ReceiverError(tr("Najpierw połącz aplikację z amplitunerem."))
        return self.receiver

    async def command(self, method: str, value):
        if method == "set_input" or (method == "set_power" and value == "standby"):
            await self._cancel_preparation()
        async with self.lock:
            receiver = self._receiver()
            if method not in {
                "set_power",
                "set_mute",
                "set_volume",
                "step_volume",
                "set_input",
                "playback",
            }:
                raise ValueError(tr("Nieznane polecenie."))
            if method == "set_input" or (method == "set_power" and value == "standby"):
                await self.audio.stop()
                await self.output_route.restore()
            return await getattr(receiver, method)(value)

    async def start_audio(
        self,
        device_index: int | None = None,
        filename: str | None = None,
        volume: int | None = None,
        route_output_id: str | None = None,
    ):
        if self._preparing:
            raise AudioError(tr("Przygotowanie przesyłania już trwa."))
        self._preparing = asyncio.current_task()
        self._observed_state = None
        self.audio.notify("preparing", tr("Przygotowywanie przesyłania…"))
        try:
            return await self._prepare_audio(device_index, filename, volume, route_output_id)
        except asyncio.CancelledError:
            self.audio.notify("stopped", tr("Przygotowanie anulowane"))
            raise
        except Exception:
            self.audio.notify("stopped", tr("Przesyłanie nie zostało uruchomione"))
            raise
        finally:
            self._preparing = None

    async def _wait_for_receiver(self, receiver, input_id=None):
        try:
            async with asyncio.timeout(_STARTUP_TIMEOUT):
                while True:
                    try:
                        snapshot = await receiver.refresh()
                    except ReceiverError:
                        await asyncio.sleep(_STATUS_POLL_INTERVAL)
                        continue
                    if snapshot.status.power == "on" and (
                        input_id is None or snapshot.status.input == input_id
                    ):
                        return snapshot
                    await asyncio.sleep(_STATUS_POLL_INTERVAL)
        except TimeoutError:
            raise AudioError(tr("Yamaha nie potwierdziła gotowości do odtwarzania.")) from None

    async def _prepare_audio(self, device_index, filename, volume, route_output_id=None):
        async with self.lock:
            receiver = self._receiver()
            if receiver.demo:
                raise AudioError(tr("Tryb demonstracyjny nie wysyła dźwięku do urządzeń."))
            if filename is None:
                _pyaudio()  # Platform/dependency check before any power change.
            if receiver.capabilities is None or "airplay" not in receiver.capabilities.inputs:
                raise AudioError(tr("Amplituner nie zgłasza wejścia AirPlay."))
            if self.audio.active:
                raise AudioError(tr("Przesyłanie jest już uruchomione."))
            snapshot = await receiver.refresh()
            if snapshot.status.power != "on":
                self.audio.notify("preparing", tr("Włączanie Yamahy…"))
                await receiver.set_power("on")
            snapshot = await self._wait_for_receiver(receiver)
            if snapshot.status.input != "airplay":
                self.audio.notify("preparing", tr("Przełączanie Yamahy na AirPlay…"))
                await receiver.set_input("airplay")
                snapshot = await self._wait_for_receiver(receiver, "airplay")

            async def confirm_receiver():
                nonlocal volume
                async with self.lock:
                    current = await receiver.refresh()
                    if current.status.power != "on":
                        raise AudioError(
                            tr("Yamaha została wyłączona podczas uruchamiania dźwięku.")
                        )
                    if current.status.input != "airplay":
                        await receiver.set_input("airplay")
                        current = await self._wait_for_receiver(receiver, "airplay")
                    if volume is not None:
                        current = await receiver.set_volume(volume)
                        volume = None
                    self.audio.diagnostics.emit(
                        "receiver_ready",
                        power=current.status.power,
                        input=current.status.input,
                        volume=current.status.volume,
                        mute=current.status.mute,
                    )

            route_options = {}
            if route_output_id and filename is None:
                await self.output_route.begin(route_output_id)
                device_index = None  # Capture the newly confirmed Windows default.
                route_options["on_finished"] = self.output_route.restore
            try:
                await self.audio.start(
                    receiver.host,
                    device_index,
                    filename,
                    on_ready=confirm_receiver,
                    **route_options,
                )
            except BaseException:
                if route_options:
                    await self.output_route.restore()
                raise
            self.audio.diagnostics.emit(
                "receiver_prepared",
                power=snapshot.status.power,
                input=snapshot.status.input,
                volume=snapshot.status.volume,
                mute=snapshot.status.mute,
            )
            return snapshot

    async def stop_audio(self):
        await self._cancel_preparation()
        async with self.lock:
            await self.audio.stop()
            await self.output_route.restore()

    async def close(self):
        await self.stop_audio()
