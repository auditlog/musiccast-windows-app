"""Run stdlib tests, with an explicit workaround for sandbox-blocked wakeup sockets."""

import argparse
import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sandbox", action="store_true", help="Poll loop when socketpair.send is denied"
    )
    args = parser.parse_args()
    if args.sandbox:
        original_runner = asyncio.Runner

        def loop_factory():
            loop = asyncio.new_event_loop()

            def tick():
                loop.call_later(0.02, tick)

            tick()
            return loop

        def runner(**kwargs):
            kwargs["loop_factory"] = loop_factory
            return original_runner(**kwargs)

        asyncio.Runner = runner
    tests = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    return 0 if unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
