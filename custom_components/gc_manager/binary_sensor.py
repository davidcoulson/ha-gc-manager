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

from .const import DOMAIN
from .entity import gc_device_info
from .gc_controller import GcController

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: GcController = hass.data[DOMAIN][entry.entry_id].controller
    async_add_entities([GcEnabledBinarySensor(entry.entry_id, controller)])


class GcEnabledBinarySensor(BinarySensorEntity):
    """Reports gc.isenabled() — whether automatic collection is running."""

    _attr_has_entity_name = True
    _attr_name = "Automatic GC enabled"
    _attr_icon = "mdi:autorenew"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str, controller: GcController) -> None:
        self._controller = controller
        self._attr_unique_id = f"{entry_id}_gc_enabled"
        self._attr_device_info = gc_device_info(entry_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._controller.async_add_listener(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        return gc.isenabled()
