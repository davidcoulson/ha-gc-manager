# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the automatic-GC-enabled binary sensor."""

from unittest.mock import MagicMock, patch

from custom_components.gc_manager.binary_sensor import (
    GcEnabledBinarySensor,
    async_setup_entry,
)


def test_is_on_reflects_gc_isenabled():
    sensor = GcEnabledBinarySensor("gcm")
    fake_gc = MagicMock()
    with patch("custom_components.gc_manager.binary_sensor.gc", fake_gc):
        fake_gc.isenabled.return_value = True
        assert sensor.is_on is True
        fake_gc.isenabled.return_value = False
        assert sensor.is_on is False


def test_unique_id_and_device():
    sensor = GcEnabledBinarySensor("gcm")
    assert sensor.unique_id == "gcm_gc_enabled"
    assert sensor.device_info is not None


async def test_platform_setup_adds_one_entity(hass):
    entry = MagicMock()
    entry.entry_id = "gcm"
    added: list = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    assert len(added) == 1
    assert isinstance(added[0], GcEnabledBinarySensor)
    assert added[0].unique_id == "gcm_gc_enabled"


def test_binary_sensor_name_is_translated():
    import json
    import pathlib

    strings = json.loads(
        pathlib.Path("custom_components/gc_manager/strings.json").read_text()
    )
    sensor = GcEnabledBinarySensor("e1")
    assert sensor.translation_key == "gc_enabled"
    assert strings["entity"]["binary_sensor"]["gc_enabled"]["name"]
