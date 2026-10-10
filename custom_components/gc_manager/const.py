# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Constants for the GC Manager integration."""

import gc
from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "gc_manager"
DEFAULT_NAME: Final = "GC Manager"
UNIQUE_ID: Final = "gc_manager_singleton"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

# ── options ──────────────────────────────────────────────────────────────────
# Freeze the long-lived heap once, just after startup, so gen-2 collections stop
# rescanning millions of permanent objects (the large-instance GC-pause fix).
CONF_FREEZE_ON_START: Final = "freeze_on_start"
DEFAULT_FREEZE_ON_START: Final = True

# On an HA *restart* the heap is still full of startup-transient objects; wait
# this long after startup completes before the first freeze so those transients
# are collected rather than frozen permanently. Only the restart path waits — an
# install or reload happens when HA is already settled, so it freezes at once.
# 0 disables the wait (freeze immediately on the started event).
CONF_STARTUP_DELAY_SECONDS: Final = "startup_delay_seconds"
DEFAULT_STARTUP_DELAY_SECONDS: Final = 120
MIN_STARTUP_DELAY_SECONDS: Final = 0
MAX_STARTUP_DELAY_SECONDS: Final = 3600

# Period of the frozen/tracked count sampler; a longer interval spreads the
# per-tick heap-walk GIL hitch out on large instances.
CONF_SAMPLE_INTERVAL_MINUTES: Final = "sample_interval_minutes"
DEFAULT_SAMPLE_INTERVAL_MINUTES: Final = 5
MIN_SAMPLE_INTERVAL_MINUTES: Final = 1
MAX_SAMPLE_INTERVAL_MINUTES: Final = 60

# Periodic collect()+freeze() to re-absorb objects accumulated since the startup
# freeze, holding the gen-2 pause near its floor. 0 = off. Rounded to a divisor
# of 24 and aligned to a wall-clock grid phased off the maintenance time (see
# refreeze_slots) so runs stay evenly spaced regardless of when HA started.
CONF_REFREEZE_INTERVAL_HOURS: Final = "refreeze_interval_hours"
# Keep automatic collection off from the moment this integration loads until
# the startup freeze has run. A start allocates millions of long-lived objects,
# and every full collection during it walks all of them (0.7-1.5 s each on a
# large instance) to find almost nothing; the startup freeze collects once,
# properly, at the end. Costs some memory for those minutes.
CONF_PAUSE_GC_UNTIL_FREEZE: Final = "pause_gc_until_freeze"
DEFAULT_PAUSE_GC_UNTIL_FREEZE: Final = False
# Automatic collection comes back after this long whatever happened, so a
# startup that never reaches its freeze cannot leave it off.
PAUSE_GC_WATCHDOG_SECONDS: Final = 900
DEFAULT_REFREEZE_INTERVAL_HOURS: Final = 6
MIN_REFREEZE_INTERVAL_HOURS: Final = 0
MAX_REFREEZE_INTERVAL_HOURS: Final = 24

# Intervals that tile a 24h day evenly; a requested interval is rounded to the
# nearest of these (ties round down, toward more-frequent).
REFREEZE_DIVISORS_OF_24: Final = (1, 2, 3, 4, 6, 8, 12, 24)

# Once a day, unfreeze()+collect()+freeze(): a full reset that reclaims anything
# that was frozen but has since become garbage (the leak the cheap re-freeze
# leaves behind), then re-freezes the current live set.
CONF_DAILY_MAINTENANCE: Final = "daily_maintenance"
DEFAULT_DAILY_MAINTENANCE: Final = True
CONF_DAILY_TIME: Final = "daily_time"
DEFAULT_DAILY_TIME: Final = "04:00:00"

# Optionally override CPython's gc thresholds — gc.set_threshold(gen0, gen1,
# gen2). Raising them makes collections rarer (but each larger); off by default,
# and the previous thresholds are restored on unload.
CONF_SET_THRESHOLDS: Final = "set_thresholds"
DEFAULT_SET_THRESHOLDS: Final = False
CONF_THRESHOLD_GEN0: Final = "threshold_gen0"
CONF_THRESHOLD_GEN1: Final = "threshold_gen1"
CONF_THRESHOLD_GEN2: Final = "threshold_gen2"
# The threshold defaults mirror whatever the running interpreter uses — which is
# exactly the gc configuration Home Assistant runs with, since HA does not change
# the CPython defaults. (CPython 3.14 itself raised the gen-0 default from 700 to
# 2000.) Reading them live keeps our defaults identical to Home Assistant's
# across Python versions rather than pinning a value that could drift.
_HASS_DEFAULT_THRESHOLDS: Final = gc.get_threshold()
DEFAULT_THRESHOLD_GEN0: Final = _HASS_DEFAULT_THRESHOLDS[0]
DEFAULT_THRESHOLD_GEN1: Final = _HASS_DEFAULT_THRESHOLDS[1]
DEFAULT_THRESHOLD_GEN2: Final = _HASS_DEFAULT_THRESHOLDS[2]

SERVICE_FREEZE: Final = "freeze"
SERVICE_UNFREEZE: Final = "unfreeze"
SERVICE_MAINTAIN: Final = "maintain"


def round_refreeze_interval(hours: int) -> int:
    """Round to a divisor of 24 so re-freezes tile a day evenly. <=0 off; >=24
    once-daily; ties round down (more frequent)."""
    if hours <= 0:
        return 0
    if hours >= 24:
        return 24
    return min(REFREEZE_DIVISORS_OF_24, key=lambda d: (abs(d - hours), d))


def refreeze_slots(
    base_hms: tuple[int, int, int],
    interval_hours: int,
    maintenance_enabled: bool,
) -> list[tuple[int, int, int]]:
    """Local (h,m,s) re-freeze slots on a 24/interval grid anchored to the
    maintenance time, so they stay evenly spaced. Skips the base slot when
    maintenance freezes there; includes it when maintenance is off."""
    step = round_refreeze_interval(interval_hours)
    if step == 0:
        return []
    base_h, base_m, base_s = base_hms
    slots: list[tuple[int, int, int]] = []
    for k in range(24 // step):
        if k == 0 and maintenance_enabled:
            continue
        slots.append(((base_h + k * step) % 24, base_m, base_s))
    return slots


def refreeze_min_gap(interval_hours: int) -> timedelta:
    """Debounce window: half the (rounded) interval, so a re-freeze closer to the
    previous freeze than to the next scheduled one is skipped (e.g. one landing
    just after the off-grid startup freeze)."""
    return timedelta(hours=round_refreeze_interval(interval_hours) / 2)


# The sensors fed by the (costly) frozen/tracked object sample.
COUNT_SENSOR_KEYS: tuple[str, ...] = ("frozen_objects", "tracked_objects")
