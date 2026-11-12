"""WASAPI loopback into a bounded WAV pipe consumed by pyatv's public stream API.

No audio is recorded to disk. The Windows output is mirrored, not muted or replaced.
"""

import asyncio
import io
import ipaddress
import logging
import math
import socket
import struct
import sys
import threading
import time
import traceback
import unicodedata
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from .credentials import AirPlayCredentials
from .diagnostics import AirPlayDiagnostics
from .health import CaptureMeter
from .i18n import tr
from .raop import configure_airplay
from .receiver import ReceiverError
from .windows_output import OutputError

log = logging.getLogger(__name__)
_RECOVERY_DELAYS = (2, 4)
_HEALTH_INTERVAL = 5
_RECEIVER_CHARACTERS = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


class AudioError(Exception):
    """Capture or AirPlay failure suitable for the UI."""


def user_audio_error(error):
    if isinstance(error, (AudioError, ReceiverError, OutputError)):
        return str(error)
    if isinstance(error, TimeoutError):
        return tr("Yamaha nie odpowiedziała na czas. Sprawdź połączenie i ponów próbę.")
    return tr("Nie udało się przesłać dźwięku. Sprawdź raport w oknie Diagnostyka.")


def _receiver_title(text):
    return unicodedata.normalize("NFC", text).translate(_RECEIVER_CHARACTERS)


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    rate: int
    channels: int


class PCMStream(io.BufferedIOBase):
    """Thread-safe, non-seekable PCM/WAV stream with bounded, frame-aligned backlog."""

    def __init__(self, rate: int, channels: int, buffer_seconds: float = 1.0, gated=False):
        super().__init__()
        if not 8000 <= rate <= 384000 or not 1 <= channels <= 8:
            raise ValueError(tr("Nieobsługiwany format dźwięku."))
        self.rate = rate
        self.channels = channels
        self.frame_size = channels * 2
        self.bytes_per_second = rate * self.frame_size
        self.capacity = max(self.frame_size, int(rate * buffer_seconds) * self.frame_size)
        self._condition = threading.Condition()
        self._chunks: deque[bytes] = deque()
        self._size = 0
        self._finished = False
        self._enabled = not gated
        self.error: str | None = None
        self.dropped_bytes = 0
        self.inserted_silence_bytes = 0
        self.underflow_reads = 0
        self.peak = 0.0
        self.name = "Windows loopback.wav"
        # RIFF's finite size is a format requirement, not a recording allocation.
        # Represents over three hours of stereo/48kHz audio before reconnecting.
        data_size = 0x7FFFF000 - (0x7FFFF000 % self.frame_size)
        self._header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            channels,
            rate,
            self.bytes_per_second,
            self.frame_size,
            16,
            b"data",
            data_size,
        )
        self._header_pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    @property
    def buffered_bytes(self) -> int:
        with self._condition:
            return self._size

    @property
    def enabled(self) -> bool:
        with self._condition:
            return self._enabled

    def enable(self):
        """Release PCM after startup confirmation and discard handshake silence."""
        with self._condition:
            if not self._finished and not self._enabled:
                self._enabled = True
                self._chunks.clear()
                self._size = 0
                self._condition.notify_all()

    def feed(self, pcm: bytes):
        if len(pcm) % self.frame_size:
            raise ValueError(tr("Niepełna ramka PCM."))
        if not pcm:
            return
        with self._condition:
            if self._finished:
                return
            if not self._enabled:
                return
            if len(pcm) > self.capacity:
                self.dropped_bytes += len(pcm) - self.capacity
                pcm = pcm[-self.capacity :]
            self._chunks.append(pcm)
            self._size += len(pcm)
            excess = max(0, self._size - self.capacity)
            to_drop = ((excess + self.frame_size - 1) // self.frame_size) * self.frame_size
            while to_drop:
                first = self._chunks.popleft()
                remove = min(len(first), to_drop)
                if remove < len(first):
                    self._chunks.appendleft(first[remove:])
                self._size -= remove
                to_drop -= remove
                self.dropped_bytes += remove
            self._condition.notify_all()

    def finish(self, error: str | None = None):
        with self._condition:
            self.error = error
            self._finished = True
            self._chunks.clear()
            self._size = 0
            self._condition.notify_all()

    def read(self, size: int = -1) -> bytes:
        if size == 0:
            return b""
        if size < 0:
            size = 8192  # Live sources never implement an unbounded read-all.
        with self._condition:
            if self._finished:
                if self.error:
                    raise AudioError(self.error)
                return b""
            header = self._header[self._header_pos : self._header_pos + size]
            self._header_pos += len(header)
            needed = size - len(header)
            # WAV parsers often request only a few header bytes. Return immediately.
            if not needed:
                return header
            # File probes and decoder setup run before RECORD. Pacing their reads
            # as live audio adds seconds to startup while the capture gate is shut.
            # Never consume captured samples here; enable() starts the live clock.
            if not self._enabled:
                return header + bytes(needed)
            # Capture callbacks can stop arriving while Windows is silent. Supply paced
            # silence, keeping the RAOP session alive instead of blocking forever.
            deadline = time.monotonic() + min(1.0, needed / self.bytes_per_second)
            while self._size < needed and not self._finished:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            if self.error:
                raise AudioError(self.error)
            if self._finished:
                return b""
            parts = [header]
            left = needed
            while left and self._chunks:
                chunk = self._chunks.popleft()
                count = min(left, len(chunk))
                parts.append(chunk[:count])
                if count < len(chunk):
                    self._chunks.appendleft(chunk[count:])
                self._size -= count
                left -= count
            if left:
                if self._enabled:
                    self.inserted_silence_bytes += left
                    self.underflow_reads += 1
                parts.append(bytes(left))
            return b"".join(parts)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self):
        self.finish()
        super().close()


class GatedFileStream(PCMStream):
    """Decode a file incrementally; do not advance it while the audio gate is shut."""

    def __init__(self, filename: str, decoder=None):
        super().__init__(44100, 2, gated=True)
        if decoder is None:
            import miniaudio

            decoder = miniaudio.stream_file(
                filename,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=2,
                sample_rate=44100,
                frames_to_read=1024,
            )
        self._decoder = iter(decoder)
        self._decoder_lock = threading.Lock()
        self._eof = False

    def read(self, size: int = -1) -> bytes:
        with self._decoder_lock:
            if self.enabled and not self._finished:
                if size < 0:
                    size = 8192
                size = min(size, self.capacity)
                header_size = len(self._header) - self._header_pos
                needed = max(0, size - header_size)
                while self.buffered_bytes < needed and not self._eof and not self._finished:
                    try:
                        samples = next(self._decoder)
                    except StopIteration:
                        self._eof = True
                    else:
                        self.feed(samples.tobytes())
                if self._finished:
                    return b""
                if self._eof:
                    size = min(size, header_size + self.buffered_bytes)
                    if not size:
                        self.finish()
                        return b""
            return super().read(size)

    def close(self):
        self.finish()
        with self._decoder_lock:
            close = getattr(self._decoder, "close", None)
            if close:
                close()
            super().close()


def _pyaudio():
    if sys.platform != "win32":
        raise AudioError(tr("Przechwytywanie dźwięku komputera jest dostępne w Windows 10/11."))
    try:
        import pyaudiowpatch
    except ImportError as error:
        raise AudioError(
            tr("Brakuje PyAudioWPatch. Uruchom ponownie instalację aplikacji.")
        ) from error
    return pyaudiowpatch


def list_audio_devices() -> list[AudioDevice]:
    pyaudio = _pyaudio()
    try:
        with pyaudio.PyAudio() as manager:
            # Loopback endpoints are appended to PortAudio's global device list.
            # Some versions omit them from the host API's device-index mapping.
            devices = [
                AudioDevice(
                    int(item["index"]),
                    str(item["name"]),
                    int(item["defaultSampleRate"]),
                    int(item["maxInputChannels"]),
                )
                for index in range(manager.get_device_count())
                if (item := manager.get_device_info_by_index(index)).get("isLoopbackDevice")
                and int(item.get("maxInputChannels", 0)) > 0
            ]
    except (OSError, ValueError) as error:
        log.exception("WASAPI output enumeration failed")
        raise AudioError(tr(
            "Nie udało się odczytać wyjść WASAPI. Sprawdź urządzenia w ustawieniach "
            "dźwięku Windows i ponownie kliknij „Odśwież wyjścia”."
        )) from error
    if not devices:
        raise AudioError(tr(
            "Windows nie udostępnił wyjść WASAPI loopback. Włącz wyjście w ustawieniach "
            "dźwięku Windows, a następnie kliknij „Odśwież wyjścia”."
        ))
    return devices


class LoopbackCapture:
    def __init__(self, device_index: int | None = None):
        self.device_index = device_index
        self.pipe: PCMStream | None = None
        self._manager = None
        self._stream = None
        self.frames_received = 0
        self.status_flags = 0
        self.meter = CaptureMeter()

    def start(self) -> PCMStream:
        pyaudio = _pyaudio()
        self._manager = pyaudio.PyAudio()
        try:
            device = (
                self._manager.get_default_wasapi_loopback()
                if self.device_index is None
                else self._manager.get_device_info_by_index(self.device_index)
            )
            if not device.get("isLoopbackDevice"):
                raise AudioError(tr("Wybrane urządzenie nie jest wyjściem WASAPI loopback."))
            self.device_index = int(device["index"])
            channels = int(device["maxInputChannels"])
            rate = int(device["defaultSampleRate"])
            self.pipe = PCMStream(rate, channels, gated=True)

            def callback(data, frame_count, time_info, status_flags):
                try:
                    self.frames_received += frame_count
                    self.status_flags |= status_flags
                    self.pipe.feed(data)
                    self.pipe.peak = self.meter.record(data)
                    return None, pyaudio.paContinue
                except Exception:
                    log.exception("Audio capture failed")
                    self.pipe.finish(tr(
                        "Błąd przechwytywania dźwięku. Odśwież wyjścia i ponów próbę."
                    ))
                    return None, pyaudio.paAbort

            self._stream = self._manager.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(device["index"]),
                frames_per_buffer=1024,
                stream_callback=callback,
            )
            return self.pipe
        except Exception:
            self.close()
            raise

    def close(self):
        if self.pipe:
            self.pipe.finish()
        stream, self._stream = self._stream, None
        manager, self._manager = self._manager, None
        if stream:
            try:
                stream.stop_stream()
            except Exception:
                log.warning("Could not stop detached WASAPI device", exc_info=True)
            finally:
                try:
                    stream.close()
                except Exception:
                    log.warning("Could not close WASAPI stream", exc_info=True)
        if manager:
            manager.terminate()


class AudioStreamer:
    """One user-started RAOP session with diagnostics and bounded recovery."""

    def __init__(
        self,
        notify: Callable[[str, str], None] | None = None,
        request_secret: Callable[[str, str], Awaitable[str | None]] | None = None,
    ):
        self.notify = notify or (lambda state, text: None)
        self.request_secret = request_secret
        self._credentials = AirPlayCredentials()
        self.diagnostics = AirPlayDiagnostics()
        self._attempt = 0
        self._recoveries = 0
        self._minimal_start = False
        self._task: asyncio.Task | None = None
        self._capture: LoopbackCapture | None = None
        self._connection = None
        self._source: PCMStream | None = None
        self._ready = False
        self.last_error: str | None = None
        self._sender_event = asyncio.Event()
        self._on_ready: Callable[[], Awaitable[None]] | None = None
        self._on_finished: Callable[[], Awaitable[None]] | None = None

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def peak(self) -> float:
        if self._capture and self._capture.pipe:
            return self._capture.pipe.peak
        return 0.0

    async def start(
        self,
        host: str,
        device_index: int | None = None,
        filename: str | None = None,
        on_ready: Callable[[], Awaitable[None]] | None = None,
        on_finished: Callable[[], Awaitable[None]] | None = None,
    ):
        if self.active:
            raise AudioError(tr("Przesyłanie dźwięku jest już uruchomione."))
        self.last_error = None
        self._sender_event.clear()
        self._attempt = 0
        self._recoveries = 0
        self._minimal_start = False
        self._on_ready = on_ready
        self._on_finished = on_finished
        self.diagnostics.start(host, "file" if filename is not None else "windows")
        if filename is not None and not await asyncio.to_thread(Path(filename).is_file):
            raise AudioError(tr("Nie znaleziono wybranego pliku dźwiękowego."))
        # Fail early before the controller wakes the device where possible.
        if filename is None:
            _pyaudio()
        try:
            import pyatv  # noqa: F401
        except ImportError as error:
            raise AudioError(
                tr("Brakuje pyatv. Uruchom instalację zależności aplikacji.")
            ) from error
        self._task = asyncio.create_task(self._run(host, device_index, filename))

    async def _run(self, host: str, device_index: int | None, filename: str | None):
        import pyatv
        from pyatv import exceptions
        from pyatv.const import PairingRequirement, Protocol

        self._ready = False
        self.notify("connecting", tr("Łączenie przez AirPlay…"))
        loop = asyncio.get_running_loop()
        try:
            self.diagnostics.emit("discovery_started")
            address = await asyncio.to_thread(socket.gethostbyname, host)
            configs = await pyatv.scan(
                loop,
                timeout=5,
                hosts=[ipaddress.ip_address(address)],
                protocol=Protocol.RAOP,
            )
            if not configs:
                raise AudioError(
                    tr("Nie wykryto AirPlay na tym adresie. Sprawdź sieć i ustawienia Yamahy.")
                )
            config = configs[0]
            service = config.get_service(Protocol.RAOP)
            if service is None:
                raise AudioError(
                    tr("Odbiornik nie udostępnił usługi AirPlay do przesyłania dźwięku.")
                )
            self.diagnostics.emit("receiver_discovered", host=address, port=service.port)
            identifier = service.identifier
            saved_password = self._credentials.read(identifier, "password")
            service.password = saved_password or service.password
            if service.requires_password and not service.password:
                service.password = await self._ask_password()
            mandatory_pairing = service.pairing == PairingRequirement.Mandatory
            saved_pairing = None
            if mandatory_pairing:
                saved_pairing = self._credentials.read(identifier, "pairing")
                service.credentials = saved_pairing or service.credentials
                if not service.credentials:
                    await self._pair(config, service)

            for attempt in range(2):
                try:
                    await self._stream_with_recovery(config, service, device_index, filename)
                except exceptions.AuthenticationError as error:
                    frames = traceback.extract_tb(error.__traceback__)
                    log.warning(
                        "AirPlay authentication rejected in %s (password supplied: %s, paired: %s)",
                        " → ".join(f"{frame.name}:{frame.lineno}" for frame in frames[-6:]),
                        bool(service.password),
                        bool(service.credentials),
                    )
                    self.diagnostics.emit("authentication_rejected")
                    if service.password:
                        self._credentials.write(identifier, "password", None)
                    if service.credentials:
                        self._credentials.write(identifier, "pairing", None)
                    if (
                        attempt
                        or (service.password and not saved_password)
                        or (service.credentials and not saved_pairing)
                        or service.pairing
                        in {PairingRequirement.Disabled, PairingRequirement.Unsupported}
                    ):
                        raise AudioError(
                            tr(
                                "Yamaha odrzuciła uwierzytelnienie AirPlay. Sprawdź hasło lub "
                                "ustawienia dostępu w amplitunerze."
                            )
                        ) from None
                    self._ready = False
                    self._sender_event.clear()
                    self.notify("connecting", tr("Odbiornik wymaga uwierzytelnienia AirPlay…"))
                    if not saved_pairing or service.password:
                        service.password = await self._ask_password(rejected=True)
                    if saved_pairing:
                        await self._pair(config, service)
                else:
                    break
        except asyncio.CancelledError:
            self.diagnostics.emit("session_cancelled")
            raise
        except Exception as error:
            frames = traceback.extract_tb(error.__traceback__)
            log.warning(
                "AirPlay stream failed: %s in %s",
                type(error).__name__,
                " → ".join(f"{frame.name}:{frame.lineno}" for frame in frames[-6:]),
            )
            self.last_error = user_audio_error(error)
            self.diagnostics.emit("session_failed", error=type(error).__name__)
            if (
                self.diagnostics.failure_operation == "RECORD session"
                and self.diagnostics.counters().get("timing_requests", 0) == 0
            ):
                self.last_error += tr(
                    " Nie zaobserwowano synchronizacji UDP z Yamahy. Sprawdź w diagnostyce "
                    "adres lokalny oraz port timing_port."
                )
                self.diagnostics.emit(
                    "no_timing_observed", reason="Check UDP reachability and Windows firewall"
                )
            self.notify("error", self.last_error)
        finally:
            self._ready = False
            self._sender_event.set()
            self.diagnostics.emit("session_stopped")
            self.notify("stopped", tr("Przesyłanie zatrzymane"))
            if self._on_finished:
                try:
                    await self._on_finished()
                except Exception as error:
                    log.exception("Could not restore Windows playback output")
                    self.notify("error", user_audio_error(error))

    async def _stream_with_recovery(self, config, service, device_index, filename):
        from pyatv import exceptions

        while True:
            self._attempt += 1
            self.diagnostics.attempt(
                self._attempt, "minimal" if self._minimal_start else "standard"
            )
            try:
                return await self._stream(config, service, device_index, filename)
            except (
                TimeoutError,
                ConnectionError,
                exceptions.ConnectionLostError,
                exceptions.ConnectionFailedError,
            ) as error:
                self.diagnostics.emit("attempt_failed", error=type(error).__name__)
                if self._recoveries == len(_RECOVERY_DELAYS):
                    self.diagnostics.emit("recovery_exhausted")
                    raise
                if self.diagnostics.airplay_version == 1 and self.diagnostics.failure_operation in {
                    "RECORD session",
                    "GET /info",
                    "POST /feedback",
                }:
                    self._minimal_start = True
                delay = _RECOVERY_DELAYS[self._recoveries]
                self._recoveries += 1
                self._ready = False
                self._sender_event.clear()
                self.diagnostics.emit(
                    "recovery_scheduled",
                    retry_in=delay,
                    reason=self.diagnostics.failure_operation,
                    profile="minimal" if self._minimal_start else "standard",
                )
                self.notify(
                    "connecting",
                    tr("Ponawianie połączenia AirPlay · próba {v0}…", v0=self._attempt + 1),
                )
                await asyncio.sleep(delay)

    async def _wait_for_stream(self, task):
        previous_packets = -1
        stalled = 0
        last_health = time.monotonic()
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=min(1.0, _HEALTH_INTERVAL))
            if done:
                break
            measurements = {
                "buffered_ms": round(
                    1000 * self._source.buffered_bytes / self._source.bytes_per_second, 1
                ),
                "inserted_silence_ms": round(
                    1000 * self._source.inserted_silence_bytes / self._source.bytes_per_second, 1
                ),
            }
            self.diagnostics.publish(**measurements)
            now = time.monotonic()
            if now - last_health < _HEALTH_INTERVAL:
                continue
            last_health = now
            counters = self.diagnostics.counters()
            self.diagnostics.emit(
                "stream_health",
                **counters,
                buffered_bytes=self._source.buffered_bytes,
                dropped_bytes=self._source.dropped_bytes,
                peak=round(self.peak, 3),
                capture_frames=self._capture.frames_received if self._capture else None,
                capture_status_flags=self._capture.status_flags if self._capture else None,
                inserted_silence_bytes=self._source.inserted_silence_bytes,
                **measurements,
                underflow_reads=self._source.underflow_reads,
                delivery_confirmed=False,
                **(self._capture.meter.snapshot() if self._capture else {}),
            )
            packets = counters.get("audio_packets", 0)
            stalled = stalled + 1 if packets == previous_packets else 0
            previous_packets = packets
            if self.diagnostics.instrumented and stalled >= 2:
                self.diagnostics.failure_operation = "audio packets"
                self.diagnostics.emit("stream_stalled")
                raise TimeoutError(tr("Nadajnik AirPlay przestał wysyłać pakiety dźwięku."))
        return await task

    async def _ask_password(self, rejected=False):
        message = (
            tr(
                "Yamaha odrzuciła połączenie AirPlay. Wpisz aktualne hasło AirPlay, jeśli"
                " go używasz."
            )
            if rejected
            else tr("Wpisz hasło AirPlay ustawione w amplitunerze.")
        )
        return await self._ask_secret(tr("Hasło AirPlay"), message)

    async def _ask_secret(self, title, text):
        if self.request_secret is None:
            raise AudioError(
                tr("Potrzebne uwierzytelnienie AirPlay. Otwórz okno aplikacji. {v0}", v0=text)
            )
        self.diagnostics.emit("authentication_input_requested")
        answer = await self.request_secret(title, text)
        if not answer:
            raise asyncio.CancelledError
        return answer

    async def _pair(self, config, service):
        import pyatv
        from pyatv import exceptions
        from pyatv.const import Protocol

        if self.request_secret is None:
            raise AudioError(tr("Odbiornik wymaga parowania AirPlay. Otwórz okno aplikacji."))
        pairing = await pyatv.pair(
            config, Protocol.RAOP, asyncio.get_running_loop(), name="MusicCast Bridge"
        )
        try:
            await asyncio.wait_for(pairing.begin(), 12)
            pin = (
                await self._ask_secret(
                    tr("Kod parowania AirPlay"), tr("Wpisz kod pokazany przez amplituner.")
                )
            ).strip()
            if not pin.isascii() or not pin.isdecimal() or len(pin) > 8:
                raise AudioError(tr("Kod parowania musi składać się z cyfr."))
            pairing.pin(int(pin))
            await asyncio.wait_for(pairing.finish(), 15)
            if not pairing.has_paired or not pairing.service.credentials:
                raise AudioError(tr("Odbiornik nie potwierdził parowania AirPlay."))
            service.credentials = pairing.service.credentials
            self._credentials.write(service.identifier, "pairing", service.credentials)
        except exceptions.PairingError:
            raise AudioError(
                tr("Parowanie AirPlay nie powiodło się. Sprawdź kod i ponów próbę.")
            ) from None
        finally:
            await pairing.close()

    def _remember_password(self, service):
        if (
            service.password
            and self._credentials.read(service.identifier, "password") != service.password
        ):
            self._credentials.write(service.identifier, "password", service.password)

    async def _stream(self, config, service, device_index, filename):
        import pyatv
        from pyatv import exceptions
        from pyatv.const import DeviceState, Protocol
        from pyatv.interface import MediaMetadata

        try:
            self._connection = await asyncio.wait_for(
                pyatv.connect(config, asyncio.get_running_loop(), protocol=Protocol.RAOP), 12
            )
            if filename is None:
                self._capture = LoopbackCapture(device_index)
                opening = asyncio.create_task(asyncio.to_thread(self._capture.start))
                try:
                    source = await asyncio.shield(opening)
                except asyncio.CancelledError:
                    # A native device open cannot be cancelled inside its OS thread.
                    # Join it before closing, otherwise it could allocate after cleanup.
                    await asyncio.gather(opening, return_exceptions=True)
                    raise
            else:
                source = await asyncio.to_thread(GatedFileStream, filename)
            self._source = source
            self.diagnostics.emit(
                "source_opened",
                rate=source.rate,
                channels=source.channels,
                device_index=self._capture.device_index if self._capture else None,
            )
            stream = self._connection.stream
            recorded = configure_airplay(
                stream, Protocol.RAOP, self.diagnostics, self._minimal_start
            )
            stream_task = asyncio.create_task(
                stream.stream_file(
                    source,
                    metadata=MediaMetadata(
                        title=_receiver_title(
                            tr("Dźwięk z komputera") if filename is None else Path(filename).name
                        )
                    ),
                )
            )
            try:
                for _ in range(120):
                    if stream_task.done():
                        break
                    if recorded is None:
                        playing = await self._connection.metadata.playing()
                        ready = playing.device_state == DeviceState.Playing
                    else:
                        ready = recorded.is_set()
                    if ready:
                        if self._on_ready is not None:
                            self.notify("connecting", tr("Potwierdzanie gotowości Yamahy…"))
                            await self._on_ready()
                        source.enable()
                        if self._capture:
                            self._capture.meter.snapshot()  # Discard handshake level measurements.
                        self._remember_password(service)
                        self._ready = True
                        self._sender_event.set()
                        self.notify("playing", tr("Przesyłanie dźwięku do Yamahy"))
                        self.diagnostics.emit("sender_ready")
                        break
                    await asyncio.sleep(0.25)
                else:
                    raise AudioError(tr("Nie udało się uruchomić nadajnika AirPlay."))
                await self._wait_for_stream(stream_task)
                if not self._ready:
                    self._remember_password(service)
            except exceptions.ProtocolError as error:
                if isinstance(
                    error.__cause__,
                    (
                        TimeoutError,
                        ConnectionError,
                        AudioError,
                        exceptions.ConnectionLostError,
                        exceptions.ConnectionFailedError,
                    ),
                ):
                    raise error.__cause__ from None
                raise
            except TimeoutError as error:
                if not str(error).startswith("no response to TEARDOWN "):
                    raise
                # pyatv awaits TEARDOWN in send_audio's finally block. Its timeout
                # wraps asyncio's timeout/cancellation, with the original error below it.
                previous = error.__context__
                while previous is not None:
                    if any(
                        frame.f_code.co_name == "send_audio"
                        for frame, _ in traceback.walk_tb(previous.__traceback__)
                    ):
                        break
                    previous = previous.__context__
                log.warning("AirPlay receiver did not acknowledge TEARDOWN")
                if not isinstance(
                    previous, (asyncio.CancelledError, exceptions.AuthenticationError)
                ):
                    # Sending TEARDOWN here means ANNOUNCE and SETUP completed.
                    self._remember_password(service)
                if previous is not None:
                    if isinstance(previous, exceptions.ProtocolError) and previous.__cause__:
                        previous = previous.__cause__
                    raise previous from None
                if filename is None:
                    raise AudioError(
                        tr(
                            "Strumień AirPlay się zakończył. Yamaha nie potwierdziła "
                            "zamknięcia sesji."
                        )
                    ) from None
            finally:
                if self._source:
                    self._source.finish()
                if not stream_task.done():
                    stream_task.cancel()
                await asyncio.gather(stream_task, return_exceptions=True)
        finally:
            try:
                if self._source:
                    await asyncio.to_thread(self._source.close)
                if self._capture:
                    await asyncio.to_thread(self._capture.close)
            except Exception:
                log.exception("WASAPI cleanup failed")
            finally:
                self._capture = None
                self._source = None
                try:
                    if self._connection:
                        tasks = self._connection.close()
                        if tasks:
                            async with asyncio.timeout(5):
                                await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    log.exception("AirPlay cleanup failed")
                finally:
                    self._connection = None
                    self.diagnostics.emit("attempt_resources_closed")

    async def stop(self):
        had_task = self._task is not None
        if self._source:
            self._source.finish()
        if self._task and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._ready = False
        self._sender_event.set()
        if had_task:
            self.notify("stopped", tr("Przesyłanie zatrzymane"))

    async def wait(self):
        """Wait for completion without polling or consuming the stored error."""
        if self._task:
            await asyncio.shield(self._task)

    async def wait_until_running(self):
        """Wait until the receiver is ready and audio is released."""
        await self._sender_event.wait()
        if not self._ready:
            raise AudioError(self.last_error or tr("Nadajnik został zatrzymany."))


def create_test_tone(path: Path, duration: float = 3.0):
    """Quiet -30dBFS stereo tone for a deliberate, manual hardware smoke test."""
    import wave

    rate = 44100
    samples = bytearray()
    for index in range(int(rate * duration)):
        envelope = min(1.0, index / (rate * 0.05), (rate * duration - index) / (rate * 0.1))
        value = int(900 * envelope * math.sin(2 * math.pi * 440 * index / rate))
        samples.extend(struct.pack("<hh", value, value))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples)
