# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""The garbage-collection control operations + a lightweight pause probe.

Python reclaims most objects immediately by reference counting; the cyclic
garbage collector's periodic *gen-2* sweep is what periodically freezes the
event loop, and its cost scales with the number of tracked objects it must
walk. ``gc.freeze()`` moves the current (long-lived) objects into a permanent
set the collector skips, which is what shrinks the pause. This controller owns
the operations that keep that effective over time (scheduling lives in
``__init__``) and a ``gc.callbacks`` timer that records the gen-2 pause.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import FROZEN_GEN2_THRESHOLD

# Only gen-2 (full) collections meaningfully pause the loop; ignore gen-0/1.
_FULL_GENERATION = 2


async def _async_wait[T](
    worker: asyncio.Future[T], completed: Callable[[T], None] | None = None
) -> T:
    """Delay cancellation until executor work (and its bookkeeping) finishes."""
    cancelled = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as err:
            cancelled = err
    result = worker.result()
    if completed is not None:
        completed(result)
    if cancelled is not None:
        raise cancelled
    return result


@dataclass(slots=True)
class GcResult:
    """Outcome of one GC operation, for logging and the diagnostic sensor."""

    action: str
    collected: int
    frozen_before: int
    frozen_after: int
    duration_ms: float
    at: datetime


class GcController:
    """Runs collect/freeze/unfreeze off the event loop and records the result.

    The collections hold the GIL while they run, so the loop is paused for their
    duration regardless of thread — the executor only keeps the operation off the
    loop's own call stack. A lock serializes the compound operations so a manual
    service call can't interleave with a scheduled one and break maintenance's
    unfreeze -> collect -> freeze guarantee.
    """

    def __init__(self, hass: HomeAssistant, logger: logging.Logger) -> None:
        self._hass = hass
        self._log = logger
        self._lock = asyncio.Lock()
        self._closing = False
        self.last_result: GcResult | None = None
        self._paused_automatic = False
        self.last_freeze_at: datetime | None = None  # last op that ended in freeze()
        # Object counts sampled off the loop — gc.get_freeze_count() walks the
        # permanent set and len(gc.get_objects()) the tracked set, both O(heap),
        # so neither may run on the event loop; refreshed on a schedule.
        self.frozen_count: int | None = None
        self.tracked_count: int | None = None
        # gen-2 pause probe. Collections are serialized (GIL / stop-the-world),
        # so start/stop pairs never overlap and these plain attributes need no
        # extra locking.
        self.last_pause_ms: float | None = None
        self.last_pause_at: datetime | None = None
        self.peak_pause_ms: float | None = None
        # Every automatic gen-2 pause since this controller started, added up.
        self.pause_count = 0
        self.pause_total_ms = 0.0
        self._pause_start: float | None = None
        # Thread of our own in-flight forced collect; the probe skips a collection
        # only on this thread, so an organic one on another thread still records.
        self._collecting_tid: int | None = None
        self._callback: Callable[[str, dict[str, Any]], None] | None = None
        self._orig_thresholds: tuple[int, int, int] | None = None
        self._overrode_thresholds = False
        # threshold2 as it was before the while-frozen raise; None = not raised.
        self._gen2_before_freeze: int | None = None

    async def async_refresh_counts(self) -> None:
        """Sample the frozen + tracked object counts off the loop.

        Both walks are O(heap) and must never run on the event loop, so the
        sensors read these cached values instead of calling gc directly.
        """

        def _counts() -> int:
            self._frozen_now()  # first sample only; the ops keep it current
            return len(gc.get_objects())

        async with self._lock:
            if self._closing:
                return
            self.tracked_count = await _async_wait(
                self._hass.async_add_executor_job(_counts)
            )

    async def async_close(self) -> None:
        """Reject new work and drain the actual worker before teardown/reload."""
        self._closing = True

        async def _drain() -> None:
            async with self._lock:
                pass

        await _async_wait(asyncio.create_task(_drain()))

    def start(self) -> None:
        """Begin timing gen-2 collections via gc.callbacks."""
        self._orig_thresholds = gc.get_threshold()
        self._callback = self._on_gc
        gc.callbacks.append(self._callback)

    def stop(self) -> None:
        if self._callback is not None and self._callback in gc.callbacks:
            gc.callbacks.remove(self._callback)
        self._callback = None

    def set_thresholds(self, gen0: int, gen1: int, gen2: int) -> None:
        """Override the automatic-collection thresholds."""
        gc.set_threshold(gen0, gen1, gen2)
        self._overrode_thresholds = True
        self._log.info("gc.set_threshold(%d, %d, %d)", gen0, gen1, gen2)

    def restore_thresholds(self) -> None:
        """Restore the captured thresholds, only if we actually overrode them."""
        if self._overrode_thresholds and self._orig_thresholds is not None:
            gc.set_threshold(*self._orig_thresholds)
            self._overrode_thresholds = False
            self._gen2_before_freeze = None  # covered by the full restore
            self._log.info("gc thresholds restored to %s", self._orig_thresholds)

    def _raise_gen2_threshold(self) -> None:
        """Keep gen-2 rare while frozen (see FROZEN_GEN2_THRESHOLD). Runs right
        after freeze(), on the executor thread."""
        gen0, gen1, gen2 = gc.get_threshold()
        if gen2 < FROZEN_GEN2_THRESHOLD:
            self._gen2_before_freeze = gen2
            gc.set_threshold(gen0, gen1, FROZEN_GEN2_THRESHOLD)

    def restore_gen2_threshold(self) -> None:
        """Undo the while-frozen raise, if it is in effect."""
        if self._gen2_before_freeze is not None:
            gen0, gen1, _ = gc.get_threshold()
            gc.set_threshold(gen0, gen1, self._gen2_before_freeze)
            self._gen2_before_freeze = None

    def _on_gc(self, phase: str, info: dict[str, Any]) -> None:
        # Runs on whichever thread triggered the collection; collections are
        # serialized, so start/stop pairs never overlap.
        if self._collecting_tid == threading.get_ident():
            return  # a collect we triggered (its callbacks fire on this thread)
        if phase == "start":
            self._pause_start = time.perf_counter()
            return
        if self._pause_start is None or info.get("generation", 0) < _FULL_GENERATION:
            return
        elapsed = (time.perf_counter() - self._pause_start) * 1000.0
        self._pause_start = None
        self.last_pause_ms = elapsed
        self.pause_count += 1
        self.pause_total_ms += elapsed
        self.last_pause_at = dt_util.utcnow()
        # Read once: a loop-thread freeze can null peak_pause_ms mid-compare, so a
        # two-read max(None, elapsed) would raise here on the collecting thread.
        peak = self.peak_pause_ms
        self.peak_pause_ms = elapsed if peak is None else max(peak, elapsed)

    def pause_automatic(self) -> bool:
        """Turn automatic collection off, if it is on. Undone by resume_automatic.

        Only ever undoes its own pause: if something else had already disabled
        the collector, it is left that way.
        """
        if self._paused_automatic or not gc.isenabled():
            return False
        gc.disable()
        self._paused_automatic = True
        self._log.info("automatic gc paused until the startup freeze")
        return True

    def resume_automatic(self) -> bool:
        """Turn automatic collection back on, if pause_automatic turned it off."""
        if not self._paused_automatic:
            return False
        self._paused_automatic = False
        gc.enable()
        self._log.info("automatic gc resumed")
        return True

    async def async_collect_and_freeze(self, action: str) -> GcResult | None:
        """collect() then freeze() — absorb current survivors into the frozen set.

        The collect clears genuine garbage first so it is not frozen permanently;
        freeze() then exempts the survivors from future sweeps.
        """
        async with self._lock:
            if self._closing:
                return None
            return await self._collect_and_freeze(action)

    async def async_refreeze_if_due(self, min_gap: timedelta) -> GcResult | None:
        """Periodic re-freeze, skipped if a freeze happened within ``min_gap``."""
        async with self._lock:
            if self._closing or self._too_soon(min_gap, "re-freeze"):
                return None
            return await self._collect_and_freeze("periodic re-freeze")

    async def async_maintain_if_due(self, min_gap: timedelta) -> GcResult | None:
        """Periodic full maintenance with the same debounce.

        Used as the periodic op when daily maintenance is disabled, so the frozen
        set is still reset and frozen-then-dead cycles are reclaimed rather than
        accumulating unbounded.
        """
        async with self._lock:
            if self._closing or self._too_soon(min_gap, "maintenance"):
                return None
            return await self._maintenance()

    async def async_maintenance(self) -> GcResult | None:
        """unfreeze() then collect() then freeze() — the no-leak full reset.

        The collect here walks the whole heap, so it is the most expensive
        operation — run it sparingly (daily).
        """
        async with self._lock:
            if self._closing:
                return None
            return await self._maintenance()

    async def async_unfreeze(self) -> GcResult | None:
        """unfreeze() — return all frozen objects to normal collection."""
        async with self._lock:
            if self._closing:
                return None

            def _do() -> GcResult:
                before = self._frozen_now()
                start = time.perf_counter()
                gc.unfreeze()
                self.restore_gen2_threshold()
                return GcResult(
                    action="unfreeze",
                    collected=0,
                    frozen_before=before,
                    frozen_after=self._frozen_after_op(),
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    at=dt_util.utcnow(),
                )

            return await self._async_execute(_do)

    def _frozen_now(self) -> int:
        """The frozen count: cached once known, since only our ops change it and
        gc.get_freeze_count() walks the whole frozen set."""
        if self.frozen_count is None:
            self.frozen_count = gc.get_freeze_count()
        return self.frozen_count

    def _frozen_after_op(self) -> int:
        self.frozen_count = gc.get_freeze_count()
        return self.frozen_count

    def _too_soon(self, min_gap: timedelta, what: str) -> bool:
        if (
            self.last_freeze_at is not None
            and dt_util.utcnow() - self.last_freeze_at < min_gap
        ):
            self._log.debug(
                "%s skipped: last freeze %s ago (< %s)",
                what,
                dt_util.utcnow() - self.last_freeze_at,
                min_gap,
            )
            return True
        return False

    async def _collect_and_freeze(self, action: str) -> GcResult:
        """collect()+freeze() body — caller must hold ``self._lock``."""

        def _do() -> GcResult:
            before = self._frozen_now()
            start = time.perf_counter()
            self._collecting_tid = threading.get_ident()
            try:
                collected = gc.collect()
            finally:
                self._collecting_tid = None
            gc.freeze()
            self._raise_gen2_threshold()
            return GcResult(
                action=action,
                collected=collected,
                frozen_before=before,
                frozen_after=self._frozen_after_op(),
                duration_ms=(time.perf_counter() - start) * 1000.0,
                at=dt_util.utcnow(),
            )

        return await self._async_execute(_do, freezes=True)

    async def _maintenance(self) -> GcResult:
        """unfreeze()+collect()+freeze() body — caller must hold ``self._lock``."""

        def _do() -> GcResult:
            before = self._frozen_now()
            start = time.perf_counter()
            gc.unfreeze()
            self._collecting_tid = threading.get_ident()
            try:
                collected = gc.collect()
            finally:
                self._collecting_tid = None
            gc.freeze()
            self._raise_gen2_threshold()
            return GcResult(
                action="daily maintenance (unfreeze+collect+freeze)",
                collected=collected,
                frozen_before=before,
                frozen_after=self._frozen_after_op(),
                duration_ms=(time.perf_counter() - start) * 1000.0,
                at=dt_util.utcnow(),
            )

        return await self._async_execute(_do, freezes=True)

    async def _async_execute(
        self, job: Callable[[], GcResult], *, freezes: bool = False
    ) -> GcResult:
        """Retain the worker and lock through cancellation; record its outcome."""

        def _completed(result: GcResult) -> None:
            self._record(result)
            if freezes:
                self.last_freeze_at = result.at
                self.peak_pause_ms = None

        return await _async_wait(self._hass.async_add_executor_job(job), _completed)

    def _record(self, result: GcResult) -> GcResult:
        self.last_result = result
        self._log.info(
            "%s: collected=%d, frozen %d->%d, took %.0fms",
            result.action,
            result.collected,
            result.frozen_before,
            result.frozen_after,
            result.duration_ms,
        )
        return result
