# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the GC control operations."""

import asyncio
import logging
import threading
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.util import dt as dt_util

from custom_components.gc_manager.gc_controller import GcController

_LOG = logging.getLogger("test")


def _const_gc():
    g = MagicMock()
    g.get_freeze_count.return_value = 5000
    g.collect.return_value = 1
    return g


def _fake_gc(freeze_counts):
    """A stand-in gc module; freeze_counts is the sequence get_freeze_count returns."""
    g = MagicMock()
    g.get_freeze_count.side_effect = list(freeze_counts)
    g.collect.return_value = 42
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


async def test_freeze_skips_the_frozen_set_counts_when_nothing_shows_them(hass):
    """get_freeze_count walks the whole frozen set holding the GIL; a freeze
    only pays for it while a sensor is enabled to show the result."""
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        controller.count_frozen = lambda: False
        result = await controller.async_collect_and_freeze("periodic re-freeze")
        g.get_freeze_count.assert_not_called()
        assert (result.frozen_before, result.frozen_after) == (None, None)
        g.collect.assert_called_once_with()
        g.freeze.assert_called_once()
        result = await controller.async_maintenance()
        g.get_freeze_count.assert_not_called()
        assert result.frozen_after is None


async def test_light_freeze_runs_a_full_collection_then_freezes(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        took = await controller.async_light_freeze()
        assert took is not None and took >= 0
        assert [
            c[0]
            for c in g.method_calls
            if c[0] in ("collect", "freeze", "get_freeze_count", "unfreeze")
        ] == ["collect", "freeze"]
        g.collect.assert_called_once_with()  # full: collect(1) froze aged garbage
        assert controller.light_freezes == 1 and controller.last_light_freeze_ms == took
        # not a freeze for the re-freeze debounce, and not news for the action sensors
        assert controller.last_freeze_at is None and controller.last_result is None


async def test_light_freeze_steps_aside_for_a_compound_operation(hass):
    g = _const_gc()
    with patch("custom_components.gc_manager.gc_controller.gc", g):
        controller = GcController(hass, _LOG)
        async with controller._lock:
            assert await controller.async_light_freeze() is None
        g.freeze.assert_not_called()
        assert controller.light_freezes == 0
