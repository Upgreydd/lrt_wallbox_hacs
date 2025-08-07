"""Wallbox sensor platform for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    ATTR_ESP_FW,
    ATTR_ATMEL_FW,
    ATTR_CHARGER_STATUS,
    ATTR_CHARGER_CURRENT_RATE,
    ATTR_CHARGER_SECONDS_SINCE_START,
    ATTR_CHARGER_CURRENT_ENERGY,
    ATTR_LAST_TRANSACTION_START_TIME,
    ATTR_LAST_TRANSACTION_END_TIME,
    ATTR_LAST_TRANSACTION_ENERGY,
)
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)

METADATA_SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    ATTR_ATMEL_FW: {
        "translation_key": "atmel_fw",
        "icon": "mdi:chip",
    },
    ATTR_ESP_FW: {
        "translation_key": "esp_fw",
        "icon": "mdi:cpu-32-bit",
    },
    ATTR_SERIAL_NUMBER: {
        "translation_key": "serial_number",
        "icon": "mdi:information-outline",
    },
    ATTR_CHARGER_STATUS: {
        "translation_key": "charger_status",
        "icon": "mdi:ev-station",
        "device_class": SensorDeviceClass.ENUM,
    },
    ATTR_CHARGER_CURRENT_RATE: {
        "translation_key": "charger_current_rate",
        "icon": "mdi:flash",
        "device_class": SensorDeviceClass.CURRENT,
        "unit": "A",
    },
    ATTR_CHARGER_SECONDS_SINCE_START: {
        "translation_key": "charger_seconds_since_start",
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "unit": "s",
    },
    ATTR_CHARGER_CURRENT_ENERGY: {
        "translation_key": "charger_current_energy",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.ENERGY,
        "unit": "kWh",
    },
    ATTR_LAST_TRANSACTION_START_TIME: {
        "translation_key": "last_transaction_start_time",
        "icon": "mdi:clock-start",
        "device_class": SensorDeviceClass.TIMESTAMP,
    },
    ATTR_LAST_TRANSACTION_END_TIME: {
        "translation_key": "last_transaction_end_time",
        "icon": "mdi:clock-end",
        "device_class": SensorDeviceClass.TIMESTAMP,
    },
    ATTR_LAST_TRANSACTION_ENERGY: {
        "translation_key": "last_transaction_energy",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.ENERGY,
        "unit": "kWh",
    },
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wallbox sensors from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    executor: WallboxClientExecutor = data["executor"]
    coordinator: DataUpdateCoordinator = data["coordinator"]

    async_add_entities(
        [
            WallboxSensor(coordinator, executor, key)
            for key in METADATA_SENSOR_DEFINITIONS
        ]
    )


class WallboxSensor(CoordinatorEntity, WallboxBaseEntity, SensorEntity):
    """Sensor for Wallbox metadata."""

    _attr_has_entity_name = True

    def __init__(
            self,
            coordinator: DataUpdateCoordinator,
            executor: WallboxClientExecutor,
            key: str,
    ) -> None:
        """Initialize the Wallbox metadata sensor."""
        super().__init__(coordinator)
        self.executor = executor
        self._key = key

        definition = METADATA_SENSOR_DEFINITIONS[key]
        self._attr_icon = definition["icon"]
        if definition.get("device_class"):
            self._attr_device_class = definition.get("device_class")
        self._attr_translation_key = definition["translation_key"]
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_unique_id = f"{executor.config_entry.entry_id}_{key}"
        self._attr_entity_category = definition.get(
            "entity_category", EntityCategory.DIAGNOSTIC
        )

    @property
    def native_value(self) -> Any:
        """Return the value of the sensor."""
        return self.executor.data.get(self._key)

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        return self.executor.last_update_success and self._key in self.executor.data
