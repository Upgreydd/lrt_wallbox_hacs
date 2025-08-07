"""Binary sensor for Wallbox network/setup/error status."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)

SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    "network_status_wlan": {
        "name": "Network Status (WLAN)",
        "translation_key": "network_status_wlan",
        "icon": "mdi:wifi",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
    },
    "network_status_ethernet": {
        "name": "Network Status (Ethernet)",
        "translation_key": "network_status_ethernet",
        "icon": "mdi:ethernet",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
    },
    "setup_status_network": {
        "name": "Setup Status (Network)",
        "translation_key": "setup_status_network",
        "icon": "mdi:network",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "setup_status_ambientLight": {
        "name": "Setup Status (Ambient Light)",
        "translation_key": "setup_status_ambientLight",
        "icon": "mdi:weather-night",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "setup_status_maxChargingPower": {
        "name": "Setup Status (Max Charging Power)",
        "translation_key": "setup_status_maxChargingPower",
        "icon": "mdi:flash",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "atmel_error": {
        "name": "Atmel Status",
        "translation_key": "atmel_error",
        "icon": "mdi:alert-circle",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    executor: WallboxClientExecutor = data["executor"]

    async_add_entities(
        [StatusBinarySensor(executor, key) for key in SENSOR_DEFINITIONS]
    )


class StatusBinarySensor(WallboxBaseEntity, BinarySensorEntity):
    """Sensor for Wallbox network/setup/error status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, executor: WallboxClientExecutor, key: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(executor)
        definition = SENSOR_DEFINITIONS[key]
        self._key = key
        self._attr_icon = definition.get("icon")
        self._attr_name = definition["name"]
        self._attr_translation_key = definition["translation_key"]
        self._attr_unique_id = f"{executor.config_entry.entry_id}_{key}"
        self._attr_device_class = definition["device_class"]

    @property
    def is_on(self) -> bool | None:
        """Return the binary state."""
        return self.executor.data.get(self._key)

    @property
    def available(self) -> bool:
        """Return True if the value is present in data."""
        return self.executor.last_update_success and self._key in self.executor.data
