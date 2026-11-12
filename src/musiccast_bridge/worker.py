"""Qt-to-asyncio bridge. Qt widgets are only accessed on the main thread."""

import asyncio
import concurrent.futures
import logging

from PySide6.QtCore import QThread, Signal

from .audio import AudioError
from .i18n import tr
from .receiver import ReceiverError
from .session import Session
from .windows_output import OutputError

log = logging.getLogger(__name__)


class Worker(QThread):
    result = Signal(str, object)
    failed = Signal(str, str)
    audio_state = Signal(str, str)
    airplay_secret = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.new_event_loop()
        self.session = Session(self.audio_state.emit, self._request_airplay_secret)

    async def _request_airplay_secret(self, title, message):
        reply = concurrent.futures.Future()
        self.airplay_secret.emit(title, message, reply)
        return await asyncio.wrap_future(reply)

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.run_until_complete(self.loop.shutdown_default_executor())
            self.loop.close()

    def submit(self, tag, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)

        def done(completed):
            try:
                self.result.emit(tag, completed.result())
            except concurrent.futures.CancelledError:
                self.result.emit(tag, None)
            except Exception as error:
                log.exception("Operation failed: %s", tag)
                message = str(error) if isinstance(
                    error, (AudioError, ReceiverError, OutputError, ValueError)
                ) else tr("Nie udało się wykonać operacji. Szczegóły zapisano w logu.")
                self.failed.emit(tag, message)

        future.add_done_callback(done)
        return future

    def shutdown(self):
        future = asyncio.run_coroutine_threadsafe(self.session.close(), self.loop)

        def stop(completed):
            try:
                completed.result()
            except Exception:
                log.exception("Audio cleanup failed")
            finally:
                self.loop.call_soon_threadsafe(self.loop.stop)

        future.add_done_callback(stop)
