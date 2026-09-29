# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the GC telemetry sensors."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.gc_manager.const import DOMAIN
from custom_components.gc_manager.sensor import (
    DESCRIPTIONS,
    GcSensor,
    async_setup_entry,
)

_AT = datetime(2026, 1, 1, 4, 0, 0, tzinfo=UTC)


def _fake_controller():
    """A controller stand-in exposing just what the value_fns read."""
    result = SimpleNamespace(
        action="startup freeze",
        at=_AT,
        collected=12_345,
        duration_ms=812.4,
        frozen_before=100,
        frozen_after=5_000_000,
    )
    return SimpleNamespace(
        frozen_count=5_000_000,
        tracked_count=800_000,  # cached attribute, sampled off the loop
        last_pause_ms=42.6,
        last_pause_at=_AT,
        peak_pause_ms=97.3,
        last_result=result,
        light_freezes=7,
        pause_count=12,
        pause_total_ms=2345.67,
        last_light_freeze_ms=3.4,
    )


def test_description_set_is_complete():
    keys = {d.key for d in DESCRIPTIONS}
    # 15 singletons (two for the light freeze, two pause totals) + 5 series × 3 generations
    assert len(DESCRIPTIONS) == 15 + 5 * 3
    assert {"frozen_objects", "tracked_objects", "last_pause", "peak_pause"} <= keys
    assert {
        "last_pause_time",
        "uncollectable_garbage",
        "last_action",
        "last_action_time",
        "last_action_reclaimed",
        "last_action_duration",
        "last_action_frozen_delta",
    } <= keys
    for gen in (0, 1, 2):
        assert {
            f"count_gen{gen}",
            f"threshold_gen{gen}",
            f"collections_gen{gen}",
            f"collected_gen{gen}",
            f"uncollectable_gen{gen}",
        } <= keys


def test_singleton_values_read_the_controller():
    controller = _fake_controller()
    by_key = {d.key: GcSensor("gcm", controller, d) for d in DESCRIPTIONS}

    assert by_key["frozen_objects"].native_value == 5_000_000
    assert by_key["tracked_objects"].native_value == 800_000
    assert by_key["last_pause"].native_value == 43  # rounded
    assert by_key["peak_pause"].native_value == 97
    assert by_key["last_pause_time"].native_value == _AT
    assert by_key["last_action"].native_value == "startup freeze"
    assert by_key["last_action_time"].native_value == _AT
    assert by_key["last_action_reclaimed"].native_value == 12_345
    assert by_key["last_action_duration"].native_value == 812  # rounded
    assert by_key["last_action_frozen_delta"].native_value == 4_999_900
    assert isinstance(by_key["uncollectable_garbage"].native_value, int)
    assert by_key["frozen_objects"].unique_id == "gcm_frozen_objects"


def test_pause_value_none_before_first_collection():
    controller = _fake_controller()
    controller.last_pause_ms = None
    controller.peak_pause_ms = None
    by_key = {d.key: GcSensor("gcm", controller, d) for d in DESCRIPTIONS}
    assert by_key["last_pause"].native_value is None
    assert by_key["peak_pause"].native_value is None


def test_last_action_none_before_any_action():
    controller = _fake_controller()
    controller.last_result = None
    by_key = {d.key: GcSensor("gcm", controller, d) for d in DESCRIPTIONS}
    assert by_key["last_action"].native_value is None
    assert by_key["last_action_time"].native_value is None
    assert by_key["last_action_reclaimed"].native_value is None
    assert by_key["last_action_duration"].native_value is None
    assert by_key["last_action_frozen_delta"].native_value is None


async def test_platform_setup_adds_every_description(hass):
    """async_setup_entry actually runs and creates one entity per description."""
    controller = _fake_controller()
    entry = MagicMock()
    entry.entry_id = "gcm"
    hass.data.setdefault(DOMAIN, {})["gcm"] = SimpleNamespace(controller=controller)
    added: list = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    assert len(added) == len(DESCRIPTIONS)
    assert all(isinstance(s, GcSensor) for s in added)
    assert {s.unique_id for s in added} == {f"gcm_{d.key}" for d in DESCRIPTIONS}


def test_per_generation_values_read_gc():
    controller = _fake_controller()
    fake_gc = MagicMock()
    fake_gc.get_count.return_value = (11, 22, 33)
    fake_gc.get_threshold.return_value = (2000, 10, 10)
    fake_gc.get_stats.return_value = [
        {"collections": 100, "collected": 1000, "uncollectable": 0},
        {"collections": 50, "collected": 500, "uncollectable": 0},
        {"collections": 5, "collected": 50, "uncollectable": 1},
    ]
    by_key = {d.key: GcSensor("gcm", controller, d) for d in DESCRIPTIONS}
    with patch("custom_components.gc_manager.sensor.gc", fake_gc):
        assert by_key["count_gen2"].native_value == 33
        assert by_key["threshold_gen0"].native_value == 2000
        assert by_key["collections_gen2"].native_value == 5
        assert by_key["collected_gen1"].native_value == 500
        assert by_key["uncollectable_gen2"].native_value == 1


def test_frozen_delta_is_unknown_when_the_counts_were_skipped():
    """A freeze that skipped the (costly) frozen-set counts has no delta."""
    desc = next(d for d in DESCRIPTIONS if d.key == "last_action_frozen_delta")
    skipped = SimpleNamespace(
        last_result=SimpleNamespace(frozen_before=None, frozen_after=None)
    )
    assert desc.value_fn(skipped) is None
    counted = SimpleNamespace(
        last_result=SimpleNamespace(frozen_before=100, frozen_after=350)
    )
    assert desc.value_fn(counted) == 250
