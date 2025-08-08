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

from .const import (
    DOMAIN,
    ATTR_SETUP_STATUS_AMBIENT_LIGHT,
    ATTR_ATMEL_ERROR,
    ATTR_NETWORK_STATUS_ETHERNET,
    ATTR_NETWORK_STATUS_WLAN,
    ATTR_SETUP_STATUS_NETWORK,
    ATTR_SETUP_STATUS_MAX_CHARGING_POWER, ATTR_CHARGING_IS_ON,
)
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)

SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    ATTR_NETWORK_STATUS_WLAN: {
        "translation_key": ATTR_NETWORK_STATUS_WLAN,
        "icon": "mdi:wifi",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
    },
    ATTR_NETWORK_STATUS_ETHERNET: {
        "translation_key": ATTR_NETWORK_STATUS_ETHERNET,
        "icon": "mdi:ethernet",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
    },
    ATTR_SETUP_STATUS_NETWORK: {
        "translation_key": ATTR_SETUP_STATUS_NETWORK,
        "icon": "mdi:network",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    ATTR_SETUP_STATUS_AMBIENT_LIGHT: {
        "translation_key": ATTR_SETUP_STATUS_AMBIENT_LIGHT,
        "icon": "mdi:weather-night",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    ATTR_SETUP_STATUS_MAX_CHARGING_POWER: {
        "translation_key": ATTR_SETUP_STATUS_MAX_CHARGING_POWER,
        "icon": "mdi:flash",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    ATTR_ATMEL_ERROR: {
        "translation_key": ATTR_ATMEL_ERROR,
        "icon": "mdi:alert-circle",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    ATTR_CHARGING_IS_ON: {
        "translation_key": ATTR_CHARGING_IS_ON,
        "icon": "mdi:ev-station",
        "device_class": BinarySensorDeviceClass.POWER,
    }
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
