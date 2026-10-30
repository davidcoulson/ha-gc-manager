"""Diagnostics download for GC Manager."""

from __future__ import annotations

import gc
import platform
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .gc_controller import GcController


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Options, interpreter GC state and the controller's cached telemetry.

    Only cached counts are reported: gc.get_freeze_count() and gc.get_objects()
    walk the heap and must not run on the event loop.
    """
    controller: GcController = hass.data[DOMAIN][entry.entry_id].controller
    last = controller.last_result
    freeze_at = controller.last_freeze_at
    pause_at = controller.last_pause_at
    return {
        "options": {**entry.data, **entry.options},
        "python_version": platform.python_version(),
        "gc": {
            "enabled": gc.isenabled(),
            "thresholds": list(gc.get_threshold()),
            "stats": gc.get_stats(),
        },
        "controller": {
            "last_result": None if last is None else last.as_dict(),
            "last_freeze_at": None if freeze_at is None else freeze_at.isoformat(),
            "frozen_count": controller.frozen_count,
            "tracked_count": controller.tracked_count,
            "last_pause_ms": controller.last_pause_ms,
            "last_pause_at": None if pause_at is None else pause_at.isoformat(),
            "peak_pause_ms": controller.peak_pause_ms,
            "pause_count": controller.pause_count,
            "pause_total_ms": controller.pause_total_ms,
        },
    }
