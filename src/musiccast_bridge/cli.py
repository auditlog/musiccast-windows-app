"""Dependency-free receiver diagnostics and explicit test-file streaming."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .audio import AudioError, create_test_tone
from .discovery import discover_receivers
from .i18n import set_language, tr
from .receiver import ReceiverError
from .session import Session
from .settings import Settings


async def run(args):
    if args.action == "discover":
        print(
            json.dumps(
                [asdict(item) for item in await discover_receivers()], ensure_ascii=False, indent=2
            )
        )
        return
    if args.action == "tone":
        create_test_tone(Path(args.file))
        print(tr("Zapisano cichy sygnał testowy: {v0}", v0=args.file))
        return
    session = Session(lambda state, text: print(f"{state}: {text}", file=sys.stderr))
    try:
        snapshot = await session.connect(args.host or "demo.local", demo=args.demo)
        if args.action == "power":
            snapshot = await session.command("set_power", args.value)
        elif args.action == "volume":
            snapshot = await session.command("set_volume", args.percent)
        elif args.action == "input":
            snapshot = await session.command("set_input", args.value)
        elif args.action == "stream":
            await session.start_audio(filename=args.file, volume=args.volume)
            await session.audio.wait_until_running()
            await session.audio.wait()
            if session.audio.last_error:
                raise AudioError(session.audio.last_error)
            return
        print(
            json.dumps(
                asdict(snapshot),
                ensure_ascii=False,
                indent=2,
                default=lambda obj: sorted(obj) if isinstance(obj, frozenset) else str(obj),
            )
        )
    finally:
        await session.close()


def main():
    set_language(Settings.load().language)
    parser = argparse.ArgumentParser(description=tr("Diagnostyka MusicCast Bridge"))
    parser.add_argument("--host", help=tr("Adres IP amplitunera"))
    parser.add_argument("--demo", action="store_true")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("discover", help=tr("Wyszukaj amplitunery w sieci"))
    commands.add_parser("status", help=tr("Odczytaj stan bez zmiany ustawień"))
    power = commands.add_parser("power")
    power.add_argument("value", choices=["on", "standby"])
    volume = commands.add_parser("volume")
    volume.add_argument("percent", type=int, choices=range(101), metavar="0–100")
    source = commands.add_parser("input")
    source.add_argument("value")
    stream = commands.add_parser("stream", help=tr("Wyślij plik przez AirPlay"))
    stream.add_argument("file")
    stream.add_argument(
        "--volume",
        type=int,
        required=True,
        choices=range(1, 101),
        metavar="1–100",
        help=tr("Jawnie wybrana głośność w procentach zakresu amplitunera"),
    )
    tone = commands.add_parser("tone", help=tr("Utwórz cichy plik WAV do testu AirPlay"))
    tone.add_argument("file")
    args = parser.parse_args()
    if args.action not in {"discover", "tone"} and not args.host and not args.demo:
        parser.error(tr("Podaj --host albo --demo"))
    try:
        asyncio.run(run(args))
    except (ReceiverError, AudioError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
