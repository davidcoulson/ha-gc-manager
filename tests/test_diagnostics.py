"""Tests for the diagnostics download."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gc_manager.const import DOMAIN
from custom_components.gc_manager.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.gc_manager.gc_controller import GcResult


async def test_diagnostics_report_options_gc_state_and_controller_telemetry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"freeze_on_start": True},
        options={"refreeze_interval_hours": 1},
        entry_id="gcm",
    )
    entry.add_to_hass(hass)
    at = datetime(2026, 10, 30, 4, 0, tzinfo=UTC)
    controller = SimpleNamespace(
        last_result=GcResult("maintenance", 12, 5000, 5100, 456.7, at),
        last_freeze_at=at,
        frozen_count=5100,
        tracked_count=90000,
        last_pause_ms=12.5,
        last_pause_at=at,
        peak_pause_ms=40.0,
        pause_count=3,
        pause_total_ms=60.0,
    )
    hass.data.setdefault(DOMAIN, {})["gcm"] = SimpleNamespace(controller=controller)
    g = MagicMock()
    g.isenabled.return_value = True
    g.get_threshold.return_value = (2000, 10, 1000)
    g.get_stats.return_value = [{"collections": 1, "collected": 2, "uncollectable": 0}]
    with patch("custom_components.gc_manager.diagnostics.gc", g):
        diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["options"] == {"freeze_on_start": True, "refreeze_interval_hours": 1}
    assert diag["python_version"].startswith("3.")
    assert diag["gc"] == {
        "enabled": True,
        "thresholds": [2000, 10, 1000],
        "stats": [{"collections": 1, "collected": 2, "uncollectable": 0}],
    }
    assert diag["controller"]["last_result"] == {
        "action": "maintenance",
        "collected": 12,
        "frozen_before": 5000,
        "frozen_after": 5100,
        "duration_ms": 456.7,
        "at": at.isoformat(),
    }
    assert diag["controller"]["frozen_count"] == 5100
    assert diag["controller"]["tracked_count"] == 90000
    assert diag["controller"]["peak_pause_ms"] == 40.0
    assert diag["controller"]["last_freeze_at"] == at.isoformat()
    g.get_freeze_count.assert_not_called()  # O(heap); use the cached count
    g.get_objects.assert_not_called()
