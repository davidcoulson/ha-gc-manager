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

# Only gen-2 (full) collections meaningfully pause the loop; ignore gen-0/1.
_FULL_GENERATION = 2


@dataclass(slots=True)
class GcResult:
    """Outcome of one GC operation, for logging and the diagnostic sensor."""

    action: str
    collected: int
    # None when the frozen set was not counted (see GcController.count_frozen).
    frozen_before: int | None
    frozen_after: int | None
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
        self.last_result: GcResult | None = None
        # gc.get_freeze_count() walks the whole frozen set holding the GIL
        # (~0.3 s at 3.5 M objects), and every freeze operation called it twice
        # just to report a delta. Asked before each operation; when it says no
        # the counts are skipped and the delta reads unknown.
        self.count_frozen: Callable[[], bool] = lambda: True
        self.light_freezes = 0
        self.last_light_freeze_ms: float | None = None
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
        self._pause_start: float | None = None
        # Thread of our own in-flight forced collect; the probe skips a collection
        # only on this thread, so an organic one on another thread still records.
        self._collecting_tid: int | None = None
        self._callback: Callable[[str, dict[str, Any]], None] | None = None
        self._orig_thresholds: tuple[int, int, int] | None = None
        self._overrode_thresholds = False

    async def async_refresh_counts(self) -> None:
        """Sample the frozen + tracked object counts off the loop.

        Both walks are O(heap) and must never run on the event loop, so the
        sensors read these cached values instead of calling gc directly.
        """

        def _counts() -> tuple[int, int]:
            return gc.get_freeze_count(), len(gc.get_objects())

        self.frozen_count, self.tracked_count = await self._hass.async_add_executor_job(
            _counts
        )

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
            self._log.info("gc thresholds restored to %s", self._orig_thresholds)

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
        self.last_pause_at = dt_util.utcnow()
        # Read once: a loop-thread freeze can null peak_pause_ms mid-compare, so a
        # two-read max(None, elapsed) would raise here on the collecting thread.
        peak = self.peak_pause_ms
        self.peak_pause_ms = elapsed if peak is None else max(peak, elapsed)

    def _frozen_count(self, counting: bool) -> int | None:
        return gc.get_freeze_count() if counting else None

    async def async_light_freeze(self) -> float | None:
        """Collect, then freeze(): keep the unfrozen set small.

        The collection is a FULL one. It is cheap here - it scans only what
        was created since the last light freeze - and it has to be full: a
        young-only collect(1) left the garbage that had already aged into the
        old generation to be frozen, and on a busy instance that is ~30,000
        objects a minute (1.8 M objects, ~800 MB, leaked in the hour it was
        tried). freeze() then moves every survivor out of the collector's
        reach. Cycles that die AFTER being frozen still wait for the daily
        maintenance, as with any freeze.

        Skipped while a compound operation holds the lock. Does not count as
        a freeze for the periodic re-freeze's debounce, and leaves the last
        action sensors alone: it runs far too often to be news.
        """
        if self._lock.locked():
            return None
        async with self._lock:

            def _do() -> float:
                start = time.perf_counter()
                self._collecting_tid = threading.get_ident()
                try:
                    gc.collect()
                finally:
                    self._collecting_tid = None
                gc.freeze()
                return (time.perf_counter() - start) * 1000.0

            took = await self._hass.async_add_executor_job(_do)
            self.light_freezes += 1
            self.last_light_freeze_ms = took
            return took

    async def async_collect_and_freeze(self, action: str) -> GcResult:
        """collect() then freeze() — absorb current survivors into the frozen set.

        The collect clears genuine garbage first so it is not frozen permanently;
        freeze() then exempts the survivors from future sweeps.
        """
        async with self._lock:
            return await self._collect_and_freeze(action)

    async def async_refreeze_if_due(self, min_gap: timedelta) -> GcResult | None:
        """Periodic re-freeze, skipped if a freeze happened within ``min_gap``."""
        async with self._lock:
            if self._too_soon(min_gap, "re-freeze"):
                return None
            return await self._collect_and_freeze("periodic re-freeze")

    async def async_maintain_if_due(self, min_gap: timedelta) -> GcResult | None:
        """Periodic full maintenance with the same debounce.

        Used as the periodic op when daily maintenance is disabled, so the frozen
        set is still reset and frozen-then-dead cycles are reclaimed rather than
        accumulating unbounded.
        """
        async with self._lock:
            if self._too_soon(min_gap, "maintenance"):
                return None
            return await self._maintenance()

    async def async_maintenance(self) -> GcResult:
        """unfreeze() then collect() then freeze() — the no-leak full reset.

        The collect here walks the whole heap, so it is the most expensive
        operation — run it sparingly (daily).
        """
        async with self._lock:
            return await self._maintenance()

    async def async_unfreeze(self) -> GcResult:
        """unfreeze() — return all frozen objects to normal collection."""
        async with self._lock:

            def _do() -> GcResult:
                counting = self.count_frozen()
                before = self._frozen_count(counting)
                start = time.perf_counter()
                gc.unfreeze()
                return GcResult(
                    action="unfreeze",
                    collected=0,
                    frozen_before=before,
                    frozen_after=self._frozen_count(counting),
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    at=dt_util.utcnow(),
                )

            return self._record(await self._hass.async_add_executor_job(_do))

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
            counting = self.count_frozen()
            before = self._frozen_count(counting)
            start = time.perf_counter()
            self._collecting_tid = threading.get_ident()
            try:
                collected = gc.collect()
            finally:
                self._collecting_tid = None
            gc.freeze()
            return GcResult(
                action=action,
                collected=collected,
                frozen_before=before,
                frozen_after=self._frozen_count(counting),
                duration_ms=(time.perf_counter() - start) * 1000.0,
                at=dt_util.utcnow(),
            )

        result = self._record(await self._hass.async_add_executor_job(_do))
        self.last_freeze_at = result.at
        self.peak_pause_ms = None
        return result

    async def _maintenance(self) -> GcResult:
        """unfreeze()+collect()+freeze() body — caller must hold ``self._lock``."""

        def _do() -> GcResult:
            counting = self.count_frozen()
            before = self._frozen_count(counting)
            start = time.perf_counter()
            gc.unfreeze()
            self._collecting_tid = threading.get_ident()
            try:
                collected = gc.collect()
            finally:
                self._collecting_tid = None
            gc.freeze()
            return GcResult(
                action="daily maintenance (unfreeze+collect+freeze)",
                collected=collected,
                frozen_before=before,
                frozen_after=self._frozen_count(counting),
                duration_ms=(time.perf_counter() - start) * 1000.0,
                at=dt_util.utcnow(),
            )

        result = self._record(await self._hass.async_add_executor_job(_do))
        self.last_freeze_at = result.at
        self.peak_pause_ms = None
        return result

    def _record(self, result: GcResult) -> GcResult:
        self.last_result = result
        self._log.info(
            "%s: collected=%d, frozen %s->%s, took %.0fms",
            result.action,
            result.collected,
            "?" if result.frozen_before is None else result.frozen_before,
            "?" if result.frozen_after is None else result.frozen_after,
            result.duration_ms,
        )
        return result
