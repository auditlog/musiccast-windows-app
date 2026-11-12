"""Connection-local diagnostics and start profiles for the pinned pyatv RAOP sender."""

import asyncio
import re
import struct
import time

from .diagnostics import AirPlayDiagnostics
from .i18n import tr

_RETRANSMIT_PACKETS = 4096


def configure_airplay(stream, protocol, trace: AirPlayDiagnostics, minimal=False):
    get_stream = getattr(stream, "get", None)
    raop = get_stream(protocol) if get_stream is not None else None
    if raop is None:
        trace.emit("protocol_hooks_unavailable")
        return None

    from pyatv.protocols.airplay.utils import AirPlayMajorVersion, get_protocol_version

    legacy = (
        get_protocol_version(raop.core.service, raop.core.settings.protocols.raop.protocol_version)
        == AirPlayMajorVersion.AirPlayV1
    )
    trace.airplay_version = 1 if legacy else 2
    recorded = asyncio.Event()
    manager = raop.playback_manager
    original_setup = manager.setup

    async def setup(service):
        manager.setup = original_setup
        client, context = await original_setup(service)
        rtsp = client.rtsp
        protocol_impl = client._protocol
        original_exchange = rtsp.exchange
        trace.instrumented = True
        trace.emit(
            "rtsp_connected",
            local_ip=rtsp.connection.local_ip,
            remote_ip=rtsp.connection.remote_ip,
            profile="minimal" if minimal and legacy else "standard",
            password_present=bool(service.password),
            paired=bool(service.credentials),
            airplay_version=1 if legacy else 2,
        )

        async def exchange(method, *args, **kwargs):
            uri = args[0] if args else kwargs.get("uri")
            target = uri if uri in {"/info", "/feedback", "/auth-setup", "*"} else "session"
            operation = f"{method} {target}"
            headers = dict(kwargs.get("headers") or {})
            if minimal and legacy and context.rtsp_session and target == "session":
                headers.setdefault("Session", context.rtsp_session)
                kwargs["headers"] = headers
            ports = {
                key: int(value)
                for key, value in re.findall(
                    r"(control_port|timing_port|server_port)=(\d+)",
                    str(headers.get("Transport", "")),
                )
            }
            rtp = {
                "rtp_seq" if key == "seq" else "rtp_time": int(value)
                for key, value in re.findall(
                    r"(seq|rtptime)=(\d+)", str(headers.get("RTP-Info", ""))
                )
            }
            trace.emit(
                "rtsp_request",
                operation=operation,
                cseq=rtsp.cseq,
                session_present="Session" in headers,
                **ports,
                **rtp,
            )
            started = time.monotonic()
            try:
                response = await original_exchange(method, *args, **kwargs)
            except asyncio.CancelledError:
                trace.emit("rtsp_cancelled", operation=operation)
                raise
            except Exception as error:
                if method != "TEARDOWN":
                    trace.failure_operation = operation
                code = getattr(error, "status_code", None)
                trace.emit(
                    "rtsp_failed",
                    operation=operation,
                    error=type(error).__name__,
                    code=code if isinstance(code, int) else None,
                    ms=round((time.monotonic() - started) * 1000),
                )
                raise
            trace.emit(
                "rtsp_response",
                operation=operation,
                code=response.code,
                ms=round((time.monotonic() - started) * 1000),
            )
            return response

        rtsp.exchange = exchange
        original_teardown = rtsp.teardown

        async def teardown(session):
            from pyatv.exceptions import ConnectionLostError

            try:
                return await asyncio.wait_for(original_teardown(session), 2)
            except (TimeoutError, ConnectionLostError):
                # Let pyatv close its RTP transport and retain the playback error
                # even when the receiver has stopped answering on the RTSP socket.
                trace.emit("teardown_unconfirmed")
                return None

        rtsp.teardown = teardown
        original_protocol_setup = protocol_impl.setup

        async def protocol_setup(*args, **kwargs):
            trace.emit(
                "udp_listening",
                control_port=client.control_client.port,
                timing_port=client.timing_server.port,
            )
            _observe_udp(client.timing_server, trace, rtsp.connection.remote_ip, timing=True)
            _observe_udp(client.control_client, trace, rtsp.connection.remote_ip)
            if legacy and hasattr(client, "_packet_backlog"):
                from pyatv.protocols.raop.fifo import PacketFifo

                # Retain ~33 s at 44.1 kHz, without adding playback latency.
                # Share the new FIFO with the sender and control listener.
                client._packet_backlog = PacketFifo(_RETRANSMIT_PACKETS)
                client.control_client.packet_backlog = client._packet_backlog
                trace.emit("retransmit_buffer", packets=_RETRANSMIT_PACKETS)
            _observe_retransmissions(client.control_client, trace, rtsp.connection.remote_ip)
            await original_protocol_setup(*args, **kwargs)
            trace.emit(
                "session_setup",
                server_port=context.server_port,
                remote_control_port=context.control_port,
                remote_timing_port=context.timing_port,
            )
            trace.emit(
                "audio_format",
                rate=context.sample_rate,
                channels=context.channels,
                sample_bits=context.bytes_per_channel * 8,
                encoding="PCM",
            )
            if legacy:
                _prime_timing(
                    client.timing_server, rtsp.connection.remote_ip, context.timing_port, trace
                )

        protocol_impl.setup = protocol_setup
        original_send_packet = protocol_impl.send_audio_packet
        previous_packet = None

        async def send_packet(transport, *args, **kwargs):
            nonlocal previous_packet
            if transport.is_closing():
                trace.emit("audio_transport_closed")
                raise ConnectionError(tr("Kanał UDP dźwięku został zamknięty."))
            result = await original_send_packet(transport, *args, **kwargs)
            now = time.monotonic()
            if previous_packet is not None:
                gap_ms = (now - previous_packet) * 1000
                trace.maximum("max_send_gap_ms", round(gap_ms, 1))
                if gap_ms > 50:
                    trace.count("send_gaps_over_50ms")
            previous_packet = now
            if trace.count("audio_packets") == 1:
                trace.emit("first_audio_packet")
            if result[0] == 65535:
                trace.emit("rtp_sequence_wrap")
            trace.count("audio_bytes", len(result[1]))
            return result

        protocol_impl.send_audio_packet = send_packet
        original_parameter = rtsp.set_parameter

        async def parameter(name, value):
            if name == "volume":
                trace.emit("volume_managed_by_receiver")
                return None
            if minimal and legacy and name == "progress":
                trace.emit("probe_skipped", operation="SET_PARAMETER progress")
                return None
            return await original_parameter(name, value)

        rtsp.set_parameter = parameter
        original_record = rtsp.record

        async def record(headers=None, body=None):
            if legacy:
                start_headers = {
                    "Session": context.rtsp_session,
                    "Range": "npt=0-",
                    "RTP-Info": f"seq={context.rtpseq};rtptime={context.rtptime}",
                }
                if headers is not None:
                    start_headers.update(headers)
                headers = start_headers
            response = await original_record(headers=headers, body=body)
            recorded.set()
            return response

        rtsp.record = record
        if minimal and legacy:

            async def info():
                trace.emit("probe_skipped", operation="GET /info")
                return {}

            async def feedback():
                trace.emit("probe_skipped", operation="POST /feedback")

            async def metadata(*args, **kwargs):
                trace.emit("probe_skipped", operation="SET_PARAMETER metadata")

            rtsp.info = info
            protocol_impl.start_feedback = feedback
            rtsp.set_metadata = metadata
        return client, context

    manager.setup = setup
    return recorded


def _prime_timing(server, remote_ip, remote_port, trace):
    if not 1 <= remote_port <= 65535:
        trace.emit("timing_probe_skipped", reason="Receiver did not provide a timing port")
        return

    from pyatv.protocols.raop.packets import TimingPacket
    from pyatv.protocols.raop.timing import ntp2parts, ntp_now

    seconds, fraction = ntp2parts(ntp_now())
    # PulseAudio's RAOP sender uses this initial timing reply before RECORD to
    # establish the UDP flow in connection-tracking firewalls. Reuse our advertised
    # timing socket so replies reach the same local port announced in SETUP.
    packet = TimingPacket.encode(
        0x80, 0xD3, 7, 0, seconds, fraction, seconds, fraction, seconds, fraction
    )
    try:
        server.transport.sendto(packet, (remote_ip, remote_port))
    except OSError as error:
        trace.emit("timing_probe_failed", error=type(error).__name__, code=error.errno)
        raise ConnectionError(
            tr("Nie udało się wysłać pakietu synchronizacji do Yamahy.")
        ) from error
    trace.emit("timing_probe_sent", timing_port=server.port, remote_timing_port=remote_port)


def _observe_udp(listener, trace, remote_ip, timing=False):
    original = listener.datagram_received

    def received(data, address):
        from_receiver = address[0] == remote_ip
        if not from_receiver or len(data) < 2:
            trace.count("ignored_udp_packets")
            return
        if not timing and data[1] & 0x7F == 0x55 and len(data) != 8:
            trace.count("ignored_udp_packets")
            return
        if from_receiver:
            counter = "timing_requests" if timing else "control_packets"
            if trace.count(counter) == 1:
                trace.emit("first_timing_request" if timing else "first_control_packet")
            if not timing and len(data) == 8 and data[1] & 0x7F == 0x55:
                sequence, packets = struct.unpack_from("!HH", data, 4)
                if trace.count("retransmit_requests") == 1:
                    trace.emit(
                        "first_retransmission_request", rtp_seq=sequence, requested_packets=packets
                    )
                trace.count("requested_packets", packets)
        try:
            original(data, address)
        except Exception as error:
            trace.emit("udp_receive_failed", error=type(error).__name__)
            raise
        if from_receiver and timing:
            trace.count("timing_replies")

    listener.datagram_received = received
    original_error = listener.error_received

    def error_received(error):
        trace.emit(
            "udp_transport_error",
            operation="timing" if timing else "control",
            error=type(error).__name__,
            code=getattr(error, "errno", None),
        )
        original_error(error)

    listener.error_received = error_received


def _observe_retransmissions(listener, trace, remote_ip):
    if not hasattr(listener, "_retransmit_lost_packets"):
        return

    def retransmit(request, address):
        if address[0] != remote_ip:
            return
        backlog = listener.packet_backlog
        start, count = request.lost_seqno, request.lost_packets
        if backlog and count:
            latest = next(reversed(tuple(backlog)))
            age = (latest - start) & 0xFFFF
            if age < 0x8000:
                trace.maximum("max_retransmit_age_packets", age)
        # Typical requests are one or a few packets. For a large range inspect
        # only the bounded FIFO instead of iterating up to 65535 sequence numbers.
        if count <= len(backlog):
            sequences = [(start + offset) & 0xFFFF for offset in range(count)]
        else:
            sequences = sorted(
                (seq for seq in backlog if (seq - start) & 0xFFFF < count),
                key=lambda seq: (seq - start) & 0xFFFF,
            )
            trace.count("retransmit_unavailable", count - len(sequences))
        for sequence in sequences:
            if sequence not in backlog:
                trace.count("retransmit_unavailable")
                continue
            packet = backlog[sequence]
            if listener.transport is None:
                trace.count("retransmit_send_errors")
                continue
            try:
                # Preserve pyatv 0.18's wire format and resend the original bytes.
                response = b"\x80\xd6" + packet[2:4] + packet
                listener.transport.sendto(response, address)
            except OSError as error:
                trace.count("retransmit_send_errors")
                trace.emit("retransmit_send_failed", error=type(error).__name__)
            else:
                # This means handed to UDP, not acknowledged or played by Yamaha.
                trace.count("retransmitted_packets")
                trace.count("retransmitted_bytes", len(response))

    listener._retransmit_lost_packets = retransmit
