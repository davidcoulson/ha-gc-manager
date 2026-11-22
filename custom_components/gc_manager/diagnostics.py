# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Diagnostics download for GC Manager."""

from __future__ import annotations

import gc
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .gc_controller import GcController


def _controller_report(controller: GcController) -> dict[str, Any]:
    last = controller.last_result
    freeze_at = controller.last_freeze_at
    pause_at = controller.last_pause_at
    return {
        "last_result": None if last is None else last.as_dict(),
        "last_freeze_at": None if freeze_at is None else freeze_at.isoformat(),
        "frozen_count": controller.frozen_count,
        "tracked_count": controller.tracked_count,
        "last_pause_ms": controller.last_pause_ms,
        "last_pause_at": None if pause_at is None else pause_at.isoformat(),
        "peak_pause_ms": controller.peak_pause_ms,
        "pause_count": controller.pause_count,
        "pause_total_ms": controller.pause_total_ms,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Stored options, interpreter GC state and the controller's cached telemetry.

    Only cached counts are reported: gc.get_freeze_count() and gc.get_objects()
    walk the heap and must not run on the event loop. Home Assistant's download
    view doesn't check that the entry is loaded, so ``controller`` is None if not.
    """
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "configured_options": {**entry.data, **entry.options},
        "gc": {
            "enabled": gc.isenabled(),
            "thresholds": list(gc.get_threshold()),
            "stats": gc.get_stats(),
        },
        "controller": None if data is None else _controller_report(data.controller),
    }
