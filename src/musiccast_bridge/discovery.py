"""Bounded local SSDP discovery; only API-confirmed Yamaha devices are returned."""

import asyncio
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from .i18n import tr
from .receiver import HttpTransport, ReceiverError


@dataclass(frozen=True)
class DiscoveredReceiver:
    host: str
    name: str
    model: str


def ssdp_candidates(timeout: float = 3.0) -> set[str]:
    hosts: set[str] = set()
    message = (
        "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n'
    ).encode("ascii")
    deadline = time.monotonic() + timeout
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.sendto(message, ("239.255.255.250", 1900))
            while time.monotonic() < deadline and len(hosts) < 64:
                sock.settimeout(max(0.01, deadline - time.monotonic()))
                try:
                    packet, sender = sock.recvfrom(16384)
                except TimeoutError:
                    break
                headers = {}
                for line in packet.decode("utf-8", errors="replace").splitlines()[1:]:
                    key, sep, value = line.partition(":")
                    if sep:
                        headers[key.strip().lower()] = value.strip()
                # Use sender address; never fetch an arbitrary LOCATION URL from a peer.
                location = urlsplit(headers.get("location", ""))
                if location.scheme == "http" and location.hostname == sender[0]:
                    hosts.add(sender[0])
    except OSError as error:
        raise ReceiverError(
            tr("Wyszukiwanie w sieci jest niedostępne. Wpisz adres IP ręcznie.")
        ) from error
    return hosts


async def discover_receivers() -> list[DiscoveredReceiver]:
    hosts = await asyncio.to_thread(ssdp_candidates)
    semaphore = asyncio.Semaphore(8)

    async def probe(host: str) -> DiscoveredReceiver | None:
        async with semaphore:
            transport = HttpTransport(host, timeout=1.2)
            try:
                info = await transport.get("system/getDeviceInfo")
            except ReceiverError:
                return None
            model = str(info.get("model_name", ""))
            if not model:
                return None
            return DiscoveredReceiver(host, model, model)

    results = await asyncio.gather(*(probe(host) for host in sorted(hosts)))
    return sorted((item for item in results if item), key=lambda item: (item.model, item.host))
