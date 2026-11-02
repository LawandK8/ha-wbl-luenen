"""Sensors: next collection date per bin, plus the next collection overall."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION
from .coordinator import WblConfigEntry, WblCoordinator

ICONS = {
    "Graue-Tonne": "mdi:trash-can",
    "Rote-Tonne": "mdi:trash-can",
    "Container-Grau": "mdi:delete-variant",
    "Container-Rot": "mdi:delete-variant",
    "Gelbe-Tonne": "mdi:recycle",
    "Gelber-Container": "mdi:recycle",
    "Bio-Tonne": "mdi:leaf",
    "Blaue-Tonne": "mdi:newspaper-variant-outline",
    "Blauer-Container": "mdi:newspaper-variant-outline",
    "Weihnachtsbaum": "mdi:pine-tree",
}

WEEKDAYS = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WblConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_bins() -> None:
        new = [key for key in coordinator.data if key not in known]
        known.update(new)
        if new:
            async_add_entities(BinSensor(coordinator, key) for key in new)

    async_add_entities([NextCollectionSensor(coordinator)])
    add_new_bins()
    entry.async_on_unload(coordinator.async_add_listener(add_new_bins))


def _days_until(day: date | None) -> int | None:
    return (day - dt_util.now().date()).days if day else None


def _when(day: date) -> str:
    days = _days_until(day)
    if days == 0:
        return "heute"
    if days == 1:
        return "morgen"
    return f"{WEEKDAYS[day.weekday()]} {day:%d.%m.}"


class BinSensor(CoordinatorEntity[WblCoordinator], SensorEntity):
    """Next collection date of one bin."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: WblCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = coordinator.name_of(key)
        self._attr_icon = ICONS.get(key, "mdi:trash-can-outline")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        return super().available and self._key in self.coordinator.data

    @property
    def native_value(self) -> date | None:
        upcoming = self.coordinator.upcoming(self._key)
        return upcoming[0] if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        upcoming = self.coordinator.upcoming(self._key)
        return {
            "days_until": _days_until(upcoming[0] if upcoming else None),
            "upcoming": [d.isoformat() for d in upcoming],
        }


class NextCollectionSensor(CoordinatorEntity[WblCoordinator], SensorEntity):
    """Next collection of any selected bin, e.g. "Bio-Tonne · Fr. 13.11."."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_collection"
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: WblCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_next"
        self._attr_device_info = coordinator.device_info

    def _next(self) -> tuple[date | None, list[str]]:
        first: date | None = None
        names: list[str] = []
        for key in self.coordinator.data:
            upcoming = self.coordinator.upcoming(key)
            if not upcoming:
                continue
            name = self.coordinator.name_of(key)
            if first is None or upcoming[0] < first:
                first, names = upcoming[0], [name]
            elif upcoming[0] == first:
                names.append(name)
        return first, names

    @property
    def native_value(self) -> str | None:
        first, names = self._next()
        if first is None:
            return None
        return f"{', '.join(names)} · {_when(first)}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        first, names = self._next()
        return {
            "date": first.isoformat() if first else None,
            "days_until": _days_until(first),
            "types": names,
        }
