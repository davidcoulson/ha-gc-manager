# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for GC Manager setup: schedule arming, services, unload, teardown."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import CoreState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gc_manager import (
    _TRACKED_SAMPLE_INTERVAL,
    _parse_hms,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.gc_manager.const import (
    CONF_DAILY_MAINTENANCE,
    CONF_FREEZE_ON_START,
    CONF_REFREEZE_INTERVAL_HOURS,
    CONF_SET_THRESHOLDS,
    CONF_STARTUP_DELAY_SECONDS,
    CONF_THRESHOLD_GEN0,
    CONF_THRESHOLD_GEN1,
    CONF_THRESHOLD_GEN2,
    DEFAULT_DAILY_TIME,
    DOMAIN,
    SERVICE_FREEZE,
    SERVICE_MAINTAIN,
    SERVICE_UNFREEZE,
    refreeze_min_gap,
    refreeze_slots,
    round_refreeze_interval,
)

_ALL_SERVICES = (SERVICE_FREEZE, SERVICE_UNFREEZE, SERVICE_MAINTAIN)

# ── pure helpers ──────────────────────────────────────────────────────────────


def test_parse_hms():
    assert _parse_hms("04:00:00") == (4, 0, 0)
    assert _parse_hms("23:30") == (23, 30, 0)
    assert _parse_hms("") == (4, 0, 0)  # default fallback
    # malformed / out-of-range falls back to the default, never raises
    assert _parse_hms("12:xx") == (4, 0, 0)
    assert _parse_hms(":30") == (4, 0, 0)
    assert _parse_hms("25:00") == (4, 0, 0)


def test_round_refreeze_interval():
    assert round_refreeze_interval(6) == 6
    assert round_refreeze_interval(0) == 0
    assert round_refreeze_interval(-3) == 0
    assert round_refreeze_interval(5) == 4  # nearest, ties round down
    assert round_refreeze_interval(7) == 6
    assert round_refreeze_interval(10) == 8
    assert round_refreeze_interval(24) == 24
    assert round_refreeze_interval(100) == 24  # clamp to once-daily


def test_refreeze_slots_phased_off_maintenance():
    assert refreeze_slots((4, 0, 0), 6, maintenance_enabled=True) == [
        (10, 0, 0),
        (16, 0, 0),
        (22, 0, 0),
    ]
    assert refreeze_slots((4, 0, 0), 6, maintenance_enabled=False) == [
        (4, 0, 0),
        (10, 0, 0),
        (16, 0, 0),
        (22, 0, 0),
    ]
    assert refreeze_slots((4, 30, 0), 5, maintenance_enabled=True) == [
        (8, 30, 0),
        (12, 30, 0),
        (16, 30, 0),
        (20, 30, 0),
        (0, 30, 0),
    ]
    assert refreeze_slots((4, 0, 0), 0, maintenance_enabled=True) == []
    assert refreeze_slots((4, 0, 0), 24, maintenance_enabled=True) == []


def test_refreeze_min_gap():
    assert refreeze_min_gap(6) == timedelta(hours=3)
    assert refreeze_min_gap(1) == timedelta(minutes=30)
    assert refreeze_min_gap(5) == timedelta(hours=2)  # rounds 5→4, then /2
    assert refreeze_min_gap(0) == timedelta(0)


# ── setup harness ─────────────────────────────────────────────────────────────


def _entry(hass, **opts):
    data = {
        CONF_FREEZE_ON_START: True,
        CONF_REFREEZE_INTERVAL_HOURS: 6,
        CONF_DAILY_MAINTENANCE: True,
        "daily_time": DEFAULT_DAILY_TIME,
        **opts,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, entry_id="gcm")
    entry.add_to_hass(hass)
    return entry


def _fake_gc():
    g = MagicMock()
    g.get_freeze_count.return_value = 5000
    g.collect.return_value = 1
    g.get_threshold.return_value = (2000, 10, 10)
    g.get_objects.return_value = []  # tracked-count sampler
    g.callbacks = []
    return g


def _patches(fake_gc, hass):
    return (
        patch("custom_components.gc_manager.gc_controller.gc", fake_gc),
        patch(
            "custom_components.gc_manager.async_track_time_change",
            return_value=MagicMock(name="timechange_unsub"),
        ),
        patch(
            "custom_components.gc_manager.async_track_time_interval",
            return_value=MagicMock(name="interval_unsub"),
        ),
        patch(
            "custom_components.gc_manager.async_call_later",
            return_value=MagicMock(name="call_later_unsub"),
        ),
        patch(
            "custom_components.gc_manager.async_at_started",
            return_value=MagicMock(name="at_started_unsub"),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    )


async def _setup(hass, entry, *, running=True):
    """Set up the entry with gc + schedulers patched, and simulate the
    async_at_started callback firing (immediately if running, else at startup)."""
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running if running else CoreState.starting)
    p_gc, p_change, p_interval, p_call_later, p_started, p_fwd = _patches(fake_gc, hass)
    with (
        p_gc,
        p_change as m_change,
        p_interval,
        p_call_later as m_cl,
        p_started as m_started,
        p_fwd,
    ):
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        if m_started.call_args is not None:  # freeze_on_start armed it
            m_started.call_args.args[1](hass)  # invoke the at-started callback
            await hass.async_block_till_done(wait_background_tasks=True)
        return fake_gc, m_change, m_cl, m_started


async def test_setup_arms_everything(hass):
    entry = _entry(hass)
    fake_gc, m_change, _cl, _started = await _setup(hass, entry)

    fake_gc.freeze.assert_called()  # startup freeze ran (install/reload path)
    hours = sorted(c.kwargs["hour"] for c in m_change.call_args_list)
    assert hours == [4, 10, 16, 22]  # daily 04:00 + re-freezes 10/16/22
    for svc in _ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, svc)


async def test_setup_respects_disabled_options(hass):
    entry = _entry(
        hass, freeze_on_start=False, refreeze_interval_hours=0, daily_maintenance=False
    )
    fake_gc, m_change, m_cl, m_started = await _setup(hass, entry)

    fake_gc.freeze.assert_not_called()
    m_change.assert_not_called()  # no re-freeze slots, no daily
    m_cl.assert_not_called()
    m_started.assert_not_called()  # freeze_on_start off → no startup hook


async def test_thresholds_applied_when_enabled(hass):
    entry = _entry(
        hass,
        **{
            CONF_SET_THRESHOLDS: True,
            CONF_THRESHOLD_GEN0: 5000,
            CONF_THRESHOLD_GEN1: 20,
            CONF_THRESHOLD_GEN2: 20,
        },
    )
    fake_gc, *_ = await _setup(hass, entry)
    fake_gc.set_threshold.assert_called_with(5000, 20, 20)


async def test_thresholds_not_applied_by_default(hass):
    entry = _entry(hass)
    fake_gc, *_ = await _setup(hass, entry)
    fake_gc.set_threshold.assert_not_called()


async def test_unload_restores_overridden_thresholds(hass):
    """An overridden gc threshold is reverted through the unload path.

    Inline so gc stays patched while async_unload_entry runs restore_thresholds."""
    entry = _entry(
        hass,
        **{
            CONF_SET_THRESHOLDS: True,
            CONF_THRESHOLD_GEN0: 5000,
            CONF_THRESHOLD_GEN1: 20,
            CONF_THRESHOLD_GEN2: 20,
        },
    )
    fake_gc = _fake_gc()  # get_threshold → (2000, 10, 10)
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.set_threshold.assert_called_with(5000, 20, 20)  # override applied
        fake_gc.set_threshold.reset_mock()
        with patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ):
            assert await async_unload_entry(hass, entry)
        fake_gc.set_threshold.assert_called_once_with(2000, 10, 10)  # reverted


async def test_count_sampler_wired_and_runs_initial_sample(hass):
    """The frozen+tracked count sampler is scheduled at _TRACKED_SAMPLE_INTERVAL
    and its initial background run populates the controller's cached counts."""
    entry = _entry(hass, freeze_on_start=False)
    fake_gc = _fake_gc()
    fake_gc.get_freeze_count.return_value = 1234
    fake_gc.get_objects.return_value = [1, 2, 3]
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval as m_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert m_interval.call_args.args[2] == _TRACKED_SAMPLE_INTERVAL
        controller = hass.data[DOMAIN][entry.entry_id].controller
        assert controller.frozen_count == 1234  # initial sample ran off the loop
        assert controller.tracked_count == 3


async def test_count_sampler_skips_while_both_count_sensors_are_disabled(hass):
    """The frozen/tracked walks hold the GIL for their whole length, so with
    both count sensors disabled there is nothing to sample for: no walk runs.
    Re-enabling either one brings the sampling back on the next tick."""
    from homeassistant.helpers import entity_registry as er

    entry = _entry(hass, freeze_on_start=False)
    reg = er.async_get(hass)
    for key in ("frozen_objects", "tracked_objects"):
        reg.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_{key}",
            config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval as m_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        controller = hass.data[DOMAIN][entry.entry_id].controller
        fake_gc.get_freeze_count.assert_not_called()
        fake_gc.get_objects.assert_not_called()
        assert controller.frozen_count is None
        # enable one: the next scheduled tick samples again
        eid = reg.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_tracked_objects"
        )
        reg.async_update_entity(eid, disabled_by=None)
        await m_interval.call_args.args[1]()
        fake_gc.get_freeze_count.assert_called_once()


async def test_light_freeze_is_scheduled_and_waits_for_the_first_freeze(hass):
    """With light_freeze_seconds set, a light freeze runs on that interval -
    but never before the heap has had its first real freeze."""
    from datetime import timedelta

    entry = _entry(hass, freeze_on_start=False, light_freeze_seconds=60)
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval as m_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        ticks = [
            c for c in m_interval.call_args_list if c.args[2] == timedelta(seconds=60)
        ]
        assert len(ticks) == 1
        controller = hass.data[DOMAIN][entry.entry_id].controller
        await ticks[0].args[1](None)
        fake_gc.freeze.assert_not_called()  # nothing frozen yet: wait
        await controller.async_collect_and_freeze("startup freeze")
        fake_gc.freeze.reset_mock()
        await ticks[0].args[1](None)
        fake_gc.collect.assert_called_with()
        fake_gc.freeze.assert_called_once()


async def test_light_freeze_is_off_by_default(hass):
    from datetime import timedelta

    entry = _entry(hass, freeze_on_start=False)
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval as m_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert all(
            c.args[2] != timedelta(seconds=60) for c in m_interval.call_args_list
        )
        assert len(m_interval.call_args_list) == 1  # only the count sampler


async def test_automatic_gc_is_off_from_setup_until_the_startup_freeze(hass):
    """On a real start with pause_gc_until_freeze, automatic collection is
    turned off at setup and back on once the startup freeze has run."""
    entry = _entry(hass, pause_gc_until_freeze=True, startup_delay_seconds=120)
    fake_gc = _fake_gc()
    fake_gc.isenabled.return_value = True
    hass.set_state(CoreState.starting)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval, p_cl as m_cl, p_started as m_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.disable.assert_called_once()
        fake_gc.enable.assert_not_called()
        m_started.call_args.args[1](hass)  # Home Assistant has started
        freeze = next(c for c in m_cl.call_args_list if c.args[1] == 120).args[2]
        fake_gc.enable.assert_not_called()  # still settling
        await freeze(None)
        fake_gc.freeze.assert_called_once()
        fake_gc.enable.assert_called_once()


async def test_the_watchdog_turns_automatic_gc_back_on(hass):
    """A start that never reaches its freeze must not leave the collector off."""
    from custom_components.gc_manager.const import PAUSE_GC_WATCHDOG_SECONDS

    entry = _entry(hass, pause_gc_until_freeze=True)
    fake_gc = _fake_gc()
    fake_gc.isenabled.return_value = True
    hass.set_state(CoreState.starting)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval, p_cl as m_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        watchdog = next(
            c for c in m_cl.call_args_list if c.args[1] == PAUSE_GC_WATCHDOG_SECONDS
        ).args[2]
        watchdog(None)
        fake_gc.enable.assert_called_once()
        watchdog(None)
        fake_gc.enable.assert_called_once()  # only ever undoes its own pause


async def test_unload_turns_automatic_gc_back_on(hass):
    entry = _entry(hass, pause_gc_until_freeze=True)
    fake_gc = _fake_gc()
    fake_gc.isenabled.return_value = True
    hass.set_state(CoreState.starting)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with (
        p_gc,
        p_change,
        p_interval,
        p_cl,
        p_started,
        p_fwd,
        patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
        ),
    ):
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.disable.assert_called_once()
        assert await async_unload_entry(hass, entry)
        fake_gc.enable.assert_called_once()


async def test_automatic_gc_is_left_alone_by_default_and_on_a_reload(hass):
    for opts, state in (
        ({}, CoreState.starting),
        ({"pause_gc_until_freeze": True}, CoreState.running),
    ):
        entry = _entry(hass, **opts)
        fake_gc = _fake_gc()
        fake_gc.isenabled.return_value = True
        hass.set_state(state)
        p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
        with p_gc, p_change, p_interval, p_cl, p_started, p_fwd:
            assert await async_setup_entry(hass, entry)
            await hass.async_block_till_done(wait_background_tasks=True)
            fake_gc.disable.assert_not_called()
        hass.data.pop(DOMAIN, None)
        await hass.config_entries.async_remove(entry.entry_id)


async def test_install_reload_freezes_immediately_no_delay(hass):
    entry = _entry(hass)
    fake_gc, _change, m_cl, _started = await _setup(hass, entry, running=True)
    fake_gc.freeze.assert_called()
    m_cl.assert_not_called()  # no settle delay on the running path


async def test_maintenance_off_periodic_does_full_maintenance(hass):
    """With daily maintenance off, the periodic pass is a full unfreeze+collect+
    freeze (so frozen-then-dead cycles don't accumulate), not a bare re-freeze.

    Inline so the captured slot action runs while gc is still patched."""
    entry = _entry(hass, daily_maintenance=False, freeze_on_start=False)
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change as m_change, p_interval, p_cl, p_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        action = m_change.call_args_list[0].args[1]  # any slot is a re-freeze
        fake_gc.unfreeze.reset_mock()
        await action(None)
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.unfreeze.assert_called()  # maintenance path, not plain re-freeze


async def test_restart_schedules_freeze_via_settle_timer(hass):
    entry = _entry(hass)  # default 120s delay
    fake_gc = _fake_gc()
    hass.set_state(CoreState.starting)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval, p_cl as m_cl, p_started as m_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.freeze.assert_not_called()
        m_cl.assert_not_called()

        m_started.call_args.args[1](hass)  # started fires
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.freeze.assert_not_called()  # deferred to the settle timer
        m_cl.assert_called_once()
        assert m_cl.call_args.args[1] == 120

        await m_cl.call_args.args[2](None)  # fire the settle timer
        await hass.async_block_till_done(wait_background_tasks=True)
        fake_gc.freeze.assert_called()


async def test_restart_zero_delay_freezes_at_startup(hass):
    entry = _entry(hass, **{CONF_STARTUP_DELAY_SECONDS: 0})
    fake_gc = _fake_gc()
    hass.set_state(CoreState.starting)
    p_gc, p_change, p_interval, p_cl, p_started, p_fwd = _patches(fake_gc, hass)
    with p_gc, p_change, p_interval, p_cl as m_cl, p_started as m_started, p_fwd:
        assert await async_setup_entry(hass, entry)
        m_started.call_args.args[1](hass)  # started fires
        await hass.async_block_till_done(wait_background_tasks=True)
        # delay 0 → freeze on the next tick (background task), not a settle timer
        m_cl.assert_not_called()
        fake_gc.freeze.assert_called()


async def test_partial_setup_failure_tears_down(hass):
    """If platform setup raises, undo the probe/thresholds/timers (no leak)."""
    entry = _entry(hass)
    fake_gc = _fake_gc()
    hass.set_state(CoreState.running)
    p_gc, p_change, p_interval, p_cl, p_started, _ = _patches(fake_gc, hass)
    with (
        p_gc,
        p_change,
        p_interval,
        p_cl,
        p_started as m_started,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        with pytest.raises(RuntimeError):
            await async_setup_entry(hass, entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert fake_gc.callbacks == []  # controller.stop() removed the probe
    # Freeze arming (async_at_started) runs only after a successful forward, so a
    # failing one never reaches it — pins the ordering (arm before forward → this
    # fails). Matters because on the running path async_at_started freezes inline.
    m_started.assert_not_called()
    assert DOMAIN not in hass.data  # shared state dropped
    for svc in _ALL_SERVICES:
        assert not hass.services.has_service(DOMAIN, svc)


async def test_remove_entry_unfreezes(hass):
    entry = _entry(hass)
    fake_gc = _fake_gc()
    with patch("custom_components.gc_manager.gc", fake_gc):
        await async_remove_entry(hass, entry)
    fake_gc.unfreeze.assert_called_once()  # restore default gc state on uninstall


async def test_unload_cancels_and_removes(hass):
    entry = _entry(hass)  # 3 re-freeze slots + 1 daily = 4 time-change unsubs
    _fg, m_change, _cl, _started = await _setup(hass, entry)

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, entry)

    assert m_change.return_value.call_count == 4  # all time-changes cancelled
    assert not hass.services.has_service(DOMAIN, SERVICE_FREEZE)
    assert DOMAIN not in hass.data
