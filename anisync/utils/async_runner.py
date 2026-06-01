"""Run async coroutines from Qt code without blocking the UI thread.

Strategy: one background thread owns a persistent asyncio loop. UI code
calls :func:`run_async(coro)` and gets back a :class:`AsyncCall` whose
``finished(result)`` / ``failed(exc)`` signals fire on the Qt main thread.

Keeping the loop alive across calls avoids per-task thread spin-up cost
and means a single shared ``httpx.AsyncClient`` per provider is safe.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Callable

from PySide6.QtCore import QObject, Signal


class AsyncCall(QObject):
    finished = Signal(object)
    failed = Signal(object)  # Exception


class _Runner:
    _instance: "_Runner | None" = None

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="anisync-async", daemon=True
        )
        self._thread.start()
        # CRITICAL: keep AsyncCall objects alive until the signal fires.
        # Without this, callers that don't store the return value get a
        # garbage-collected QObject and Qt segfaults emitting onto freed
        # memory.
        self._inflight: set[AsyncCall] = set()
        self._inflight_lock = threading.Lock()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @classmethod
    def instance(cls) -> "_Runner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def submit(self, coro: Awaitable[Any]) -> AsyncCall:
        call = AsyncCall()
        with self._inflight_lock:
            self._inflight.add(call)
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

        def _release() -> None:
            with self._inflight_lock:
                self._inflight.discard(call)

        # Release after the queued signal has had a chance to run on the
        # main thread (deleteLater-style). Connect at queued connection
        # type by emitting from worker thread — Qt cross-thread signal
        # auto-queues to the receiver's thread.
        call.finished.connect(lambda _r: _release())
        call.failed.connect(lambda _e: _release())

        def _done(fut) -> None:  # type: ignore[no-untyped-def]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                try:
                    call.failed.emit(exc)
                except RuntimeError:
                    pass
            else:
                try:
                    call.finished.emit(res)
                except RuntimeError:
                    pass

        future.add_done_callback(_done)
        return call


def run_async(
    coro: Awaitable[Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> AsyncCall:
    call = _Runner.instance().submit(coro)
    if on_done:
        call.finished.connect(on_done)
    if on_error:
        call.failed.connect(on_error)
    return call


def shutdown() -> None:
    if _Runner._instance is None:
        return
    loop = _Runner._instance.loop
    loop.call_soon_threadsafe(loop.stop)
