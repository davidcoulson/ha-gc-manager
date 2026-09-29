# Copyright (c) 2026 Kenneth Baker <bakerkj@umich.edu>
# All rights reserved.

"""Comprehensive GC telemetry sensors.

Every value the ``gc`` module exposes is published as its own time series so it
can be recorded and reassessed later, rather than hidden in attributes: the
frozen/tracked object counts, the gen-2 pause (from the controller's probe),
the current per-generation counts, the thresholds, and the cumulative
collections / collected / uncollectable stats per generation.
"""

from __future__ import annotations

import gc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import gc_device_info
from .gc_controller import GcController

# gc state moves slowly; a 5-minute poll keeps the recorder light. The two
# heap-walking values (frozen + tracked object counts) are sampled off the loop
# by the controller, so the poll itself reads cheap cached/counter values.
SCAN_INTERVAL = timedelta(minutes=5)

_OBJECTS = "objects"
_COLLECTIONS = "collections"


@dataclass(frozen=True, kw_only=True)
class GcSensorDescription(SensorEntityDescription):
    """A GC sensor description carrying the value getter."""

    value_fn: Callable[[GcController], StateType | datetime]


def _ms(value: float | None) -> int | None:
    return None if value is None else round(value)


_SINGLETON: tuple[GcSensorDescription, ...] = (
    GcSensorDescription(
        key="frozen_objects",
        name="Frozen objects",
        icon="mdi:snowflake",
        native_unit_of_measurement=_OBJECTS,
        state_class=SensorStateClass.MEASUREMENT,
        # Cached off-loop sample — gc.get_freeze_count() walks the permanent set.
        value_fn=lambda c: c.frozen_count,
    ),
    GcSensorDescription(
        key="tracked_objects",
        name="Tracked objects",
        icon="mdi:counter",
        native_unit_of_measurement=_OBJECTS,
        state_class=SensorStateClass.MEASUREMENT,
        # Cached off-loop sample — the tracked-set walk is O(heap).
        value_fn=lambda c: c.tracked_count,
    ),
    GcSensorDescription(
        key="last_pause",
        name="Last gen-2 pause",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _ms(c.last_pause_ms),
    ),
    GcSensorDescription(
        key="peak_pause",
        name="Peak gen-2 pause since freeze",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _ms(c.peak_pause_ms),
    ),
    GcSensorDescription(
        key="last_pause_time",
        name="Last gen-2 pause time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.last_pause_at,
    ),
    GcSensorDescription(
        key="uncollectable_garbage",
        name="Uncollectable garbage",
        icon="mdi:delete-alert",
        native_unit_of_measurement=_OBJECTS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: len(gc.garbage),
    ),
    GcSensorDescription(
        key="last_action",
        name="Last GC action",
        icon="mdi:history",
        value_fn=lambda c: c.last_result.action if c.last_result else None,
    ),
    GcSensorDescription(
        key="last_action_time",
        name="Last GC action time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.last_result.at if c.last_result else None,
    ),
    GcSensorDescription(
        key="last_action_reclaimed",
        name="Last action reclaimed",
        icon="mdi:broom",
        native_unit_of_measurement=_OBJECTS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.last_result.collected if c.last_result else None,
    ),
    GcSensorDescription(
        key="last_action_duration",
        name="Last action duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: round(c.last_result.duration_ms) if c.last_result else None,
    ),
    GcSensorDescription(
        key="last_action_frozen_delta",
        name="Last action frozen delta",
        icon="mdi:snowflake-variant",
        native_unit_of_measurement=_OBJECTS,
        state_class=SensorStateClass.MEASUREMENT,
        # Unknown when the operation skipped the (costly) frozen-set counts.
        value_fn=lambda c: (
            c.last_result.frozen_after - c.last_result.frozen_before
            if c.last_result
            and c.last_result.frozen_after is not None
            and c.last_result.frozen_before is not None
            else None
        ),
    ),
    GcSensorDescription(
        key="pause_count",
        name="Gen-2 pauses",
        icon="mdi:pause-circle-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.pause_count,
    ),
    GcSensorDescription(
        key="pause_total",
        name="Gen-2 pause time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda c: round(c.pause_total_ms, 1),
    ),
    GcSensorDescription(
        key="light_freezes",
        name="Light freezes",
        icon="mdi:snowflake-melt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.light_freezes,
    ),
    GcSensorDescription(
        key="last_light_freeze_duration",
        name="Last light freeze duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda c: c.last_light_freeze_ms,
    ),
)


def _count(gen: int) -> Callable[[GcController], StateType]:
    return lambda _c: gc.get_count()[gen]


def _threshold(gen: int) -> Callable[[GcController], StateType]:
    return lambda _c: gc.get_threshold()[gen]


def _stat(gen: int, field: str) -> Callable[[GcController], StateType]:
    return lambda _c: gc.get_stats()[gen][field]


def _per_generation() -> list[GcSensorDescription]:
    """One sensor per generation for current count, threshold, and the three
    cumulative stats — so each is an independently recorded series."""
    out: list[GcSensorDescription] = []
    for gen in (0, 1, 2):
        out.append(
            GcSensorDescription(
                key=f"count_gen{gen}",
                name=f"Gen-{gen} count",
                native_unit_of_measurement=_OBJECTS,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_count(gen),
            )
        )
        out.append(
            GcSensorDescription(
                key=f"threshold_gen{gen}",
                name=f"Gen-{gen} threshold",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_threshold(gen),
            )
        )
        out.append(
            GcSensorDescription(
                key=f"collections_gen{gen}",
                name=f"Gen-{gen} collections",
                native_unit_of_measurement=_COLLECTIONS,
                state_class=SensorStateClass.TOTAL_INCREASING,
                value_fn=_stat(gen, "collections"),
            )
        )
        out.append(
            GcSensorDescription(
                key=f"collected_gen{gen}",
                name=f"Gen-{gen} collected",
                native_unit_of_measurement=_OBJECTS,
                state_class=SensorStateClass.TOTAL_INCREASING,
                value_fn=_stat(gen, "collected"),
            )
        )
        out.append(
            GcSensorDescription(
                key=f"uncollectable_gen{gen}",
                name=f"Gen-{gen} uncollectable",
                native_unit_of_measurement=_OBJECTS,
                state_class=SensorStateClass.TOTAL_INCREASING,
                value_fn=_stat(gen, "uncollectable"),
            )
        )
    return out


DESCRIPTIONS: tuple[GcSensorDescription, ...] = _SINGLETON + tuple(_per_generation())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: GcController = hass.data[DOMAIN][entry.entry_id].controller
    async_add_entities(
        GcSensor(entry.entry_id, controller, desc) for desc in DESCRIPTIONS
    )


class GcSensor(SensorEntity):
    """One GC telemetry value."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: GcSensorDescription

    def __init__(
        self, entry_id: str, controller: GcController, description: GcSensorDescription
    ) -> None:
        self.entity_description = description
        self._controller = controller
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = gc_device_info(entry_id)

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self._controller)
