# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Binary sensor: whether automatic garbage collection is enabled."""

from __future__ import annotations

import gc
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import gc_device_info

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([GcEnabledBinarySensor(entry.entry_id)])


class GcEnabledBinarySensor(BinarySensorEntity):
    """Reports gc.isenabled() — whether automatic collection is running."""

    _attr_has_entity_name = True
    _attr_translation_key = "gc_enabled"
    _attr_icon = "mdi:autorenew"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str) -> None:
        self._attr_unique_id = f"{entry_id}_gc_enabled"
        self._attr_device_info = gc_device_info(entry_id)

    @property
    def is_on(self) -> bool:
        return gc.isenabled()
