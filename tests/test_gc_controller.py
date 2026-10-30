# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the GC control operations."""

import asyncio
import logging
import threading
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.gc_manager.const import FROZEN_GEN2_THRESHOLD
from custom_components.gc_manager.gc_controller import GcController

_LOG = logging.getLogger("test")


def _const_gc():
    g = MagicMock()
    g.get_freeze_count.return_value = 5000
    g.collect.return_value = 1
    g.get_threshold.return_value = (2000, 10, 10)
    return g


def _fake_gc(freeze_counts):
    """A stand-in gc module; freeze_counts is the sequence get_freeze_count returns."""
    g = MagicMock()
    g.get_freeze_count.side_effect = list(freeze_counts)
    g.collect.return_value = 42
    g.get_threshold.return_value = (2000, 10, 10)
    return g


async def test_collect_and_freeze_runs_collect_then_freeze(hass):
    g = _fake_gc([100, 5000])  # before, after
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        result = await controller.async_collect_and_freeze("startup freeze")

    g.collect.assert_called_once()
    g.freeze.assert_called_once()
    g.unfreeze.assert_not_called()
    assert [c[0] for c in g.method_calls] == [
        "get_freeze_count",
        "collect",
        "freeze",
        "get_threshold",
        "set_threshold",  # gen-2 threshold raised while frozen
        "get_freeze_count",
    ]
    assert result.action == "startup freeze"
    assert result.collected == 42
    assert (result.frozen_before, result.frozen_after) == (100, 5000)
    assert controller.last_result is result


async def test_maintenance_unfreezes_then_collects_then_freezes(hass):
    g = _fake_gc([5000, 4800])
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        result = await controller.async_maintenance()

    # order matters: unfreeze must precede collect so dead frozen objects are swept
    assert [c[0] for c in g.method_calls] == [
        "get_freeze_count",
        "unfreeze",
        "collect",
        "freeze",
        "get_threshold",
        "set_threshold",  # gen-2 threshold raised while frozen
        "get_freeze_count",
    ]
    assert "unfreeze+collect+freeze" in result.action


async def test_unfreeze_only(hass):
    g = _fake_gc([5000, 0])
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        result = await controller.async_unfreeze()

    g.unfreeze.assert_called_once()
    g.collect.assert_not_called()
    g.freeze.assert_not_called()
    assert result.action == "unfreeze"


async def test_last_freeze_at_tracks_only_freezes(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        c = GcController(hass, _LOG)
        assert c.last_freeze_at is None
        await c.async_collect_and_freeze("startup freeze")
        first = c.last_freeze_at
        assert first is not None
        await c.async_unfreeze()
        assert c.last_freeze_at == first  # unfreeze must not count as a freeze
        await c.async_maintenance()
        assert c.last_freeze_at is not None and c.last_freeze_at >= first


async def test_peak_pause_resets_after_freeze(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        c = GcController(hass, _LOG)
        c._on_gc("start", {"generation": 2})
        c._on_gc("stop", {"generation": 2})
        assert c.peak_pause_ms is not None  # an organic gen-2 pause was recorded
        await c.async_collect_and_freeze("startup freeze")
        assert c.peak_pause_ms is None  # "peak since freeze" reset by the freeze


async def test_refreeze_if_due_skips_when_recent(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        c = GcController(hass, _LOG)
        await c.async_collect_and_freeze("startup freeze")  # last_freeze_at = now
        g.freeze.reset_mock()
        assert await c.async_refreeze_if_due(timedelta(hours=3)) is None
        g.freeze.assert_not_called()


async def test_refreeze_if_due_runs_when_unset_or_stale(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        c = GcController(hass, _LOG)
        # never frozen → runs
        result = await c.async_refreeze_if_due(timedelta(hours=3))
        assert result is not None and result.action == "periodic re-freeze"
        # force the last freeze stale → runs again
        g.freeze.reset_mock()
        c.last_freeze_at = dt_util.utcnow() - timedelta(hours=4)
        assert await c.async_refreeze_if_due(timedelta(hours=3)) is not None
        g.freeze.assert_called()


async def test_start_registers_callback_and_captures_thresholds(hass):
    g = MagicMock()
    g.callbacks = []
    g.get_threshold.return_value = (700, 10, 10)
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()
        assert controller._callback in g.callbacks
        assert controller._orig_thresholds == (700, 10, 10)
        controller.stop()
        assert controller._callback is None
        assert g.callbacks == []


async def test_probe_times_only_gen2(hass):
    g = MagicMock()
    g.callbacks = []
    g.get_threshold.return_value = (700, 10, 10)
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()

        # a gen-0/1 collection is ignored by the probe
        controller._on_gc("start", {"generation": 0})
        controller._on_gc("stop", {"generation": 0})
        assert controller.last_pause_ms is None

        # a gen-2 collection is recorded as last + peak
        controller._on_gc("start", {"generation": 2})
        controller._on_gc("stop", {"generation": 2})
        assert controller.last_pause_ms is not None
        assert controller.peak_pause_ms == controller.last_pause_ms


async def test_set_and_restore_thresholds(hass):
    g = MagicMock()
    g.callbacks = []
    g.get_threshold.return_value = (2000, 10, 10)
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()  # captures (2000, 10, 10)
        controller.set_thresholds(5000, 20, 20)
        g.set_threshold.assert_called_with(5000, 20, 20)
        controller.restore_thresholds()
        g.set_threshold.assert_called_with(2000, 10, 10)


async def test_restore_thresholds_noop_when_not_overridden(hass):
    g = MagicMock()
    g.callbacks = []
    g.get_threshold.return_value = (2000, 10, 10)
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()  # captures a baseline but never overrides
        g.set_threshold.reset_mock()
        controller.restore_thresholds()
        g.set_threshold.assert_not_called()  # don't revert what we never changed


async def test_on_gc_ignores_own_collect_but_records_other_threads(hass):
    g = MagicMock()
    g.callbacks = []
    g.get_threshold.return_value = (2000, 10, 10)
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()
        # a collect we triggered fires its callbacks on our own thread → ignored
        controller._collecting_tid = threading.get_ident()
        controller._on_gc("start", {"generation": 2})
        controller._on_gc("stop", {"generation": 2})
        assert controller.last_pause_ms is None
        # an organic collect on another thread during our window is still recorded
        controller._collecting_tid = threading.get_ident() + 1
        controller._on_gc("start", {"generation": 2})
        controller._on_gc("stop", {"generation": 2})
        assert controller.last_pause_ms is not None


async def test_async_refresh_counts_samples_off_loop(hass):
    g = MagicMock()
    g.get_freeze_count.return_value = 1234
    g.get_objects.return_value = [1, 2, 3, 4]
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        assert controller.frozen_count is None and controller.tracked_count is None
        with patch.object(
            hass, "async_add_executor_job", wraps=hass.async_add_executor_job
        ) as m_exec:
            await controller.async_refresh_counts()
        # the O(heap) walks must be dispatched off the loop, not run inline
        m_exec.assert_called_once()
        assert controller.frozen_count == 1234
        assert controller.tracked_count == 4


async def test_maintain_if_due_runs_and_debounces(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        result = await controller.async_maintain_if_due(timedelta(hours=3))
        assert result is not None and "unfreeze+collect+freeze" in result.action
        g.unfreeze.assert_called()
        g.reset_mock()
        # a freeze just happened → the next one is debounced
        assert await controller.async_maintain_if_due(timedelta(hours=3)) is None
        g.unfreeze.assert_not_called()


async def test_lock_serializes_compound_ops(hass):
    """Concurrent compound ops must not interleave (else maintenance's
    unfreeze->collect->freeze can be defeated by another op's freeze).

    collect() sleeps, holding the executor job open — so without the lock the
    second op (on another executor thread) would interleave; the assertion of
    two clean sequences only holds because the lock serializes them.
    """
    g = MagicMock()
    g.get_freeze_count.return_value = 5000
    g.get_threshold.return_value = (2000, 10, 10)
    order: list[str] = []

    def _rec(name):
        def _fn(*_a, **_k):
            order.append(name)
            if name == "collect":
                time.sleep(0.05)  # keep the op open long enough to interleave
            return 1

        return _fn

    g.unfreeze.side_effect = _rec("unfreeze")
    g.collect.side_effect = _rec("collect")
    g.freeze.side_effect = _rec("freeze")
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        await asyncio.gather(
            controller.async_maintenance(), controller.async_maintenance()
        )
    assert order == ["unfreeze", "collect", "freeze", "unfreeze", "collect", "freeze"]


def test_gen2_pauses_are_counted_and_added_up(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        for _ in range(3):
            controller._on_gc("start", {"generation": 2})
            controller._on_gc("stop", {"generation": 2})
        controller._on_gc("start", {"generation": 0})
        controller._on_gc("stop", {"generation": 0})  # young collections are not pauses
        assert controller.pause_count == 3
        assert (
            controller.pause_total_ms >= 0
            and controller.pause_total_ms == pytest.approx(controller.pause_total_ms)
        )


async def test_freeze_raises_gen2_threshold_and_unfreeze_restores_it(hass):
    """A frozen heap trips CPython's gen-2 "25% pending" guard on nearly every
    gen-1 pass, so threshold2 is raised while frozen and put back on unfreeze."""
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        await controller.async_collect_and_freeze("startup freeze")
        g.set_threshold.assert_called_once_with(2000, 10, FROZEN_GEN2_THRESHOLD)
        g.get_threshold.return_value = (2000, 10, FROZEN_GEN2_THRESHOLD)
        await controller.async_maintenance()  # re-freeze: already raised, no-op
        g.set_threshold.assert_called_once()
        await controller.async_unfreeze()
        g.set_threshold.assert_called_with(2000, 10, 10)  # the pre-freeze value


async def test_restore_thresholds_also_undoes_the_gen2_raise(hass):
    g = _const_gc()
    g.callbacks = []
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.start()  # captures (2000, 10, 10)
        controller.set_thresholds(5000, 20, 20)
        g.get_threshold.return_value = (5000, 20, 20)
        await controller.async_collect_and_freeze("startup freeze")
        g.set_threshold.reset_mock()
        controller.restore_thresholds()
        controller.restore_gen2_threshold()  # nothing left to undo
        g.set_threshold.assert_called_once_with(2000, 10, 10)


@pytest.mark.parametrize("operation", ["freeze", "maintenance", "unfreeze"])
async def test_cancellation_holds_lock_until_worker_finishes(hass, operation):
    g = _const_gc()
    entered, release = threading.Event(), threading.Event()

    def _blocked():
        entered.set()
        assert release.wait(5)
        return 1

    if operation == "unfreeze":
        g.unfreeze.side_effect = _blocked
    else:
        g.collect.side_effect = _blocked
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        operations = {
            "freeze": lambda: controller.async_collect_and_freeze("cancelled freeze"),
            "maintenance": controller.async_maintenance,
            "unfreeze": controller.async_unfreeze,
        }
        task = asyncio.create_task(operations[operation]())
        follower = None
        try:
            assert await hass.async_add_executor_job(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()  # repeated cancellation must not abandon the worker either
            await asyncio.sleep(0)
            follower = asyncio.create_task(controller.async_unfreeze())
            await asyncio.sleep(0)
            assert not task.done()
            assert not follower.done()
            assert controller._lock.locked()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            if follower is not None:
                await follower
        assert controller.last_result.action == "unfreeze"
        if operation != "unfreeze":
            assert controller.last_freeze_at is not None
            names = [call[0] for call in g.method_calls]
            assert names.index("freeze") < len(names) - 2
        else:
            assert controller.last_freeze_at is None


async def test_close_drains_worker_and_rejects_queued_operations(hass):
    g = _const_gc()
    entered, release = threading.Event(), threading.Event()

    def _collect():
        entered.set()
        assert release.wait(5)
        return 1

    g.collect.side_effect = _collect
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        task = asyncio.create_task(controller.async_collect_and_freeze("in flight"))
        queued = close = None
        try:
            assert await hass.async_add_executor_job(entered.wait, 2)
            queued = asyncio.create_task(controller.async_maintenance())
            await asyncio.sleep(0)
            close = asyncio.create_task(controller.async_close())
            await asyncio.sleep(0)
            close.cancel()
            await asyncio.sleep(0)
            assert not close.done()
        finally:
            release.set()
            result = await task
            if queued is not None:
                assert await queued is None
            if close is not None:
                with pytest.raises(asyncio.CancelledError):
                    await close
        assert controller.last_result is result
        assert controller.last_freeze_at == result.at
        assert not controller._lock.locked()
        g.collect.assert_called_once()
        g.freeze.assert_called_once()
        g.unfreeze.assert_not_called()


async def test_frozen_count_is_walked_once_then_carried_between_ops(hass):
    """gc.get_freeze_count() walks the whole frozen set, and only our own ops
    change it — so after the first walk each op reads the cached value as its
    'before' and refreshes the cache with its single 'after' walk."""
    g = _fake_gc([100, 5000, 7000])
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        r1 = await controller.async_collect_and_freeze("a")
        r2 = await controller.async_collect_and_freeze("b")
        await controller.async_refresh_counts()  # no further frozen-set walk
    assert (r1.frozen_before, r1.frozen_after) == (100, 5000)
    assert (r2.frozen_before, r2.frozen_after) == (5000, 7000)
    assert g.get_freeze_count.call_count == 3
    assert controller.frozen_count == 7000
