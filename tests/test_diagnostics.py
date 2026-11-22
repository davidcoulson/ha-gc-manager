# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the diagnostics download."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gc_manager.const import DOMAIN
from custom_components.gc_manager.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.gc_manager.gc_controller import GcController, GcResult


def _entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"freeze_on_start": True},
        options={"refreeze_interval_hours": 1},
        entry_id="gcm",
    )
    entry.add_to_hass(hass)
    return entry


async def test_diagnostics_report_options_gc_state_and_controller_telemetry(hass):
    entry = _entry(hass)
    at = datetime(2026, 10, 30, 4, 0, tzinfo=UTC)
    controller = GcController(hass, MagicMock())
    controller.last_result = GcResult("maintenance", 12, 5000, 5100, 456.7, at)
    controller.last_freeze_at = at
    controller.frozen_count = 5100
    controller.tracked_count = 90000
    controller.last_pause_ms = 12.5
    controller.last_pause_at = at
    controller.peak_pause_ms = 40.0
    controller.pause_count = 3
    controller.pause_total_ms = 60.0
    hass.data.setdefault(DOMAIN, {})["gcm"] = SimpleNamespace(controller=controller)
    g = MagicMock()
    g.isenabled.return_value = True
    g.get_threshold.return_value = (2000, 10, 1000)
    g.get_stats.return_value = [{"collections": 1, "collected": 2, "uncollectable": 0}]
    with patch("custom_components.gc_manager.diagnostics.gc", g):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["configured_options"] == {
        "freeze_on_start": True,
        "refreeze_interval_hours": 1,
    }
    assert diag["gc"] == {
        "enabled": True,
        "thresholds": [2000, 10, 1000],
        "stats": [{"collections": 1, "collected": 2, "uncollectable": 0}],
    }
    assert diag["controller"] == {
        "last_result": {
            "action": "maintenance",
            "collected": 12,
            "frozen_before": 5000,
            "frozen_after": 5100,
            "duration_ms": 456.7,
            "at": at.isoformat(),
        },
        "last_freeze_at": at.isoformat(),
        "frozen_count": 5100,
        "tracked_count": 90000,
        "last_pause_ms": 12.5,
        "last_pause_at": at.isoformat(),
        "peak_pause_ms": 40.0,
        "pause_count": 3,
        "pause_total_ms": 60.0,
    }
    json.dumps(diag)  # the download is JSON
    g.get_freeze_count.assert_not_called()  # O(heap); use the cached count
    g.get_objects.assert_not_called()


async def test_diagnostics_for_an_entry_that_is_not_loaded(hass):
    entry = _entry(hass)
    # hass.data has no DOMAIN key at all, as after the last entry's teardown.
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["controller"] is None
    assert diag["configured_options"]["refreeze_interval_hours"] == 1
    assert "thresholds" in diag["gc"]
    json.dumps(diag)
