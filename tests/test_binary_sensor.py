# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Tests for the automatic-GC-enabled binary sensor."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.gc_manager.binary_sensor import (
    GcEnabledBinarySensor,
    async_setup_entry,
)
from custom_components.gc_manager.const import DOMAIN
from custom_components.gc_manager.gc_controller import GcController


def _controller():
    return SimpleNamespace(async_add_listener=MagicMock(return_value=lambda: None))


def test_is_on_reflects_gc_isenabled():
    sensor = GcEnabledBinarySensor("gcm", _controller())
    fake_gc = MagicMock()
    with patch("custom_components.gc_manager.binary_sensor.gc", fake_gc):
        fake_gc.isenabled.return_value = True
        assert sensor.is_on is True
        fake_gc.isenabled.return_value = False
        assert sensor.is_on is False


def test_unique_id_and_device():
    sensor = GcEnabledBinarySensor("gcm", _controller())
    assert sensor.unique_id == "gcm_gc_enabled"
    assert sensor.device_info is not None


async def test_platform_setup_adds_one_entity(hass):
    entry = MagicMock()
    entry.entry_id = "gcm"
    hass.data.setdefault(DOMAIN, {})["gcm"] = SimpleNamespace(controller=_controller())
    added: list = []
    await async_setup_entry(hass, entry, lambda new: added.extend(new))
    assert len(added) == 1
    assert isinstance(added[0], GcEnabledBinarySensor)
    assert added[0].unique_id == "gcm_gc_enabled"


async def test_binary_sensor_state_is_pushed_on_pause_and_resume(hass):
    g = MagicMock()
    g.isenabled.return_value = True
    with (
        patch("custom_components.gc_manager.gc_controller.gc", g),
        patch("custom_components.gc_manager.binary_sensor.gc", g),
    ):
        controller = GcController(hass, MagicMock())
        sensor = GcEnabledBinarySensor("gcm", controller)
        sensor.hass = hass
        sensor.entity_id = "binary_sensor.gc_manager_automatic_gc_enabled"
        with patch.object(sensor, "async_write_ha_state") as write:
            await sensor.async_added_to_hass()
            controller.pause_automatic()
            controller.resume_automatic()
            assert write.call_count == 2
