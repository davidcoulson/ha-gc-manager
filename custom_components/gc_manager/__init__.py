# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""The GC Manager integration.

Schedules the garbage-collection operations that keep gen-2 pauses small on a
large Home Assistant instance: a freeze just after startup, an optional periodic
re-freeze, and an optional daily unfreeze+collect+freeze reset. The operations
themselves live in :class:`GcController`.
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started

from .const import (
    CONF_DAILY_MAINTENANCE,
    CONF_DAILY_TIME,
    CONF_FREEZE_ON_START,
    CONF_PAUSE_GC_UNTIL_FREEZE,
    CONF_REFREEZE_INTERVAL_HOURS,
    CONF_SAMPLE_INTERVAL_MINUTES,
    CONF_SET_THRESHOLDS,
    CONF_STARTUP_DELAY_SECONDS,
    CONF_THRESHOLD_GEN0,
    CONF_THRESHOLD_GEN1,
    CONF_THRESHOLD_GEN2,
    COUNT_SENSOR_KEYS,
    DEFAULT_DAILY_MAINTENANCE,
    DEFAULT_DAILY_TIME,
    DEFAULT_FREEZE_ON_START,
    DEFAULT_PAUSE_GC_UNTIL_FREEZE,
    DEFAULT_REFREEZE_INTERVAL_HOURS,
    DEFAULT_SAMPLE_INTERVAL_MINUTES,
    DEFAULT_SET_THRESHOLDS,
    DEFAULT_STARTUP_DELAY_SECONDS,
    DEFAULT_THRESHOLD_GEN0,
    DEFAULT_THRESHOLD_GEN1,
    DEFAULT_THRESHOLD_GEN2,
    DOMAIN,
    PAUSE_GC_WATCHDOG_SECONDS,
    PLATFORMS,
    SERVICE_FREEZE,
    SERVICE_MAINTAIN,
    SERVICE_UNFREEZE,
    refreeze_min_gap,
    refreeze_slots,
    round_refreeze_interval,
)
from .gc_controller import GcController

_LOGGER = logging.getLogger(__name__)

_SERVICES = (SERVICE_FREEZE, SERVICE_UNFREEZE, SERVICE_MAINTAIN)

# Cadence for sampling the (heap-walking) non-frozen tracked-object count, done
# off the loop so the sensor read itself is cheap.


@dataclass
class GcManagerData:
    controller: GcController
    unsubs: list[Callable[[], None]] = field(default_factory=list)


def _parse_hms(value: str) -> tuple[int, int, int]:
    """Parse an ``HH:MM``/``HH:MM:SS`` value to (h, m, s).

    Malformed or out-of-range input (only reachable via hand-edited config, not a
    TimeSelector) falls back to the default instead of crashing setup.
    """
    for candidate in (value, DEFAULT_DAILY_TIME):
        try:
            parts = str(candidate or "").split(":")
            nums = [int(p) for p in parts[:3]] + [0, 0, 0]
            h, m, s = nums[0], nums[1], nums[2]
        except ValueError:
            continue
        if 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60:
            return h, m, s
    return 0, 0, 0  # unreachable: DEFAULT_DAILY_TIME is always valid


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GC Manager and arm its schedules."""
    source = {**entry.data, **entry.options}
    controller = GcController(hass, _LOGGER)
    data = GcManagerData(controller=controller)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    controller.start()  # begin the gen-2 pause probe; captures original thresholds

    try:
        _arm_entry(hass, entry, data, source)
        _register_services(hass, controller)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        # Arm the startup freeze only after setup has succeeded: it can dispatch
        # an immediate freeze, and _teardown cannot recall an already-dispatched
        # one — so a failing forward_entry_setups must happen first.
        _arm_startup_freeze(hass, entry, data, source)
    except Exception:
        # A failed setup is not followed by async_unload_entry, so undo the
        # global gc state (callback + thresholds) and timers ourselves; otherwise
        # a transient platform error would leak a dangling probe and overridden
        # thresholds, and each reload would stack another callback.
        _teardown(hass, entry, data)
        raise

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


@callback
def _arm_startup_freeze(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: GcManagerData,
    source: dict,
) -> None:
    """Arm the one-shot startup freeze (may dispatch immediately)."""
    if not source.get(CONF_FREEZE_ON_START, DEFAULT_FREEZE_ON_START):
        return

    controller = data.controller
    was_running = hass.state is CoreState.running
    delay = int(source.get(CONF_STARTUP_DELAY_SECONDS, DEFAULT_STARTUP_DELAY_SECONDS))

    async def _startup_freeze(_arg=None) -> None:
        try:
            await controller.async_collect_and_freeze("startup freeze")
        finally:
            controller.resume_automatic()

    # Only on a real start: on an install or reload the freeze is immediate and
    # there is no startup to get through.
    pause_wanted = not was_running and source.get(
        CONF_PAUSE_GC_UNTIL_FREEZE, DEFAULT_PAUSE_GC_UNTIL_FREEZE
    )
    if pause_wanted and controller.pause_automatic():

        @callback
        def _watchdog(_now) -> None:
            if controller.resume_automatic():
                _LOGGER.warning(
                    "startup freeze had not run after %ds; automatic gc resumed",
                    PAUSE_GC_WATCHDOG_SECONDS,
                )

        data.unsubs.append(async_call_later(hass, PAUSE_GC_WATCHDOG_SECONDS, _watchdog))

    @callback
    def _on_started(_hass: HomeAssistant) -> None:
        # Install/reload (already up) freezes immediately; a real restart waits
        # the settle delay so startup-transient objects are collected rather than
        # frozen permanently. Never runs mid-boot.
        if was_running or delay <= 0:
            entry.async_create_background_task(
                hass, _startup_freeze(), "gc_manager_startup_freeze"
            )
        else:
            data.unsubs.append(async_call_later(hass, delay, _startup_freeze))

    # async_at_started fires immediately if HA is already started (closing the
    # race where the started event fired before we could subscribe).
    data.unsubs.append(async_at_started(hass, _on_started))


@callback
def _arm_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: GcManagerData,
    source: dict,
) -> None:
    """Apply the threshold override (if any) and arm all schedules."""
    controller = data.controller

    # ── gc threshold override (optional) ───────────────────────────────────
    if source.get(CONF_SET_THRESHOLDS, DEFAULT_SET_THRESHOLDS):
        controller.set_thresholds(
            int(source.get(CONF_THRESHOLD_GEN0, DEFAULT_THRESHOLD_GEN0)),
            int(source.get(CONF_THRESHOLD_GEN1, DEFAULT_THRESHOLD_GEN1)),
            int(source.get(CONF_THRESHOLD_GEN2, DEFAULT_THRESHOLD_GEN2)),
        )

    # ── off-loop sampling of the frozen + tracked object counts ────────────
    # Off the loop is not free: both walks hold the GIL for their whole length
    # (~0.3 s for gc.get_freeze_count() with ~3.5 M frozen objects on Python
    # 3.14), so the event loop stalls while they run all the same. The counts
    # feed only the two count sensors, so while both are disabled there is
    # nothing to sample for.
    @callback
    def _counts_wanted() -> bool:
        registry = er.async_get(hass)
        for key in COUNT_SENSOR_KEYS:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}"
            )
            if entity_id is None:
                return True  # not registered yet (first start): sample
            reg_entry = registry.async_get(entity_id)
            if reg_entry is not None and reg_entry.disabled_by is None:
                return True
        return False

    async def _sample_counts(_now=None) -> None:
        if not _counts_wanted():
            return
        await controller.async_refresh_counts()

    sample_interval = timedelta(
        minutes=int(
            source.get(CONF_SAMPLE_INTERVAL_MINUTES, DEFAULT_SAMPLE_INTERVAL_MINUTES)
        )
    )
    data.unsubs.append(async_track_time_interval(hass, _sample_counts, sample_interval))
    entry.async_create_background_task(
        hass, _sample_counts(), "gc_manager_sample_counts"
    )

    maintenance_enabled = bool(
        source.get(CONF_DAILY_MAINTENANCE, DEFAULT_DAILY_MAINTENANCE)
    )
    base_hms = _parse_hms(source.get(CONF_DAILY_TIME, DEFAULT_DAILY_TIME))

    # ── periodic re-freeze (wall-clock grid, phased off the maintenance time) ─
    refreeze_hours = int(
        source.get(CONF_REFREEZE_INTERVAL_HOURS, DEFAULT_REFREEZE_INTERVAL_HOURS)
    )
    slots = refreeze_slots(base_hms, refreeze_hours, maintenance_enabled)
    if slots:
        min_gap = refreeze_min_gap(refreeze_hours)
        # With daily maintenance on, the periodic pass is a cheap re-freeze; with
        # it off, the periodic pass does the full unfreeze+collect+freeze so
        # frozen-then-dead cycles don't accumulate unbounded.
        refreeze_op = (
            controller.async_refreeze_if_due
            if maintenance_enabled
            else controller.async_maintain_if_due
        )

        async def _refreeze(_now) -> None:
            await refreeze_op(min_gap)

        for hour, minute, second in slots:
            data.unsubs.append(
                async_track_time_change(
                    hass, _refreeze, hour=hour, minute=minute, second=second
                )
            )
        _LOGGER.info(
            "re-freeze every %dh (requested %d) at local %s%s",
            round_refreeze_interval(refreeze_hours),
            refreeze_hours,
            ", ".join(f"{h:02d}:{m:02d}" for h, m, _ in slots),
            "" if maintenance_enabled else " (full maintenance; daily off)",
        )

    # ── daily maintenance (unfreeze + collect + freeze) ────────────────────
    if maintenance_enabled:
        hour, minute, second = base_hms

        async def _daily(_now) -> None:
            await controller.async_maintenance()

        data.unsubs.append(
            async_track_time_change(
                hass, _daily, hour=hour, minute=minute, second=second
            )
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down schedules and services."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    data: GcManagerData = hass.data[DOMAIN][entry.entry_id]
    _teardown(hass, entry, data)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """On uninstall, restore default gc state by undoing any freeze we applied.

    Unload (incl. reload) deliberately leaves the heap frozen for continuity;
    only true removal reverts it, off the loop.
    """
    await hass.async_add_executor_job(gc.unfreeze)


@callback
def _teardown(hass: HomeAssistant, entry: ConfigEntry, data: GcManagerData) -> None:
    """Cancel timers, remove the probe, restore thresholds, drop shared state."""
    for unsub in data.unsubs:
        unsub()
    data.unsubs.clear()
    data.controller.resume_automatic()
    data.controller.restore_thresholds()
    data.controller.stop()

    domain_data = hass.data.get(DOMAIN)
    if domain_data is not None:
        domain_data.pop(entry.entry_id, None)
        if not domain_data:
            hass.data.pop(DOMAIN, None)
            for service in _SERVICES:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _register_services(hass: HomeAssistant, controller: GcController) -> None:
    """Register the manual freeze/unfreeze/maintain services (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_FREEZE):
        return

    async def _freeze(_call: ServiceCall) -> None:
        await controller.async_collect_and_freeze("manual freeze (service)")

    async def _unfreeze(_call: ServiceCall) -> None:
        await controller.async_unfreeze()

    async def _maintain(_call: ServiceCall) -> None:
        await controller.async_maintenance()

    hass.services.async_register(DOMAIN, SERVICE_FREEZE, _freeze)
    hass.services.async_register(DOMAIN, SERVICE_UNFREEZE, _unfreeze)
    hass.services.async_register(DOMAIN, SERVICE_MAINTAIN, _maintain)
