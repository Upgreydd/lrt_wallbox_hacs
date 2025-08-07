"""This module defines a number entity for controlling the maximum current limit."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)

MIN_CURRENT = 6


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wallbox number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    executor: WallboxClientExecutor = data["executor"]
    coordinator: DataUpdateCoordinator = data["coordinator"]

    max_load = entry.data.get("max_load", 16)

    async_add_entities([WallboxLoadLimitNumber(coordinator, executor, max_load)])


class WallboxLoadLimitNumber(CoordinatorEntity, WallboxBaseEntity, NumberEntity):
    """Representation of a Wallbox max load number entity."""

    _attr_has_entity_name = True
    _attr_name = "Max Current Limit"
    _attr_icon = "mdi:flash"
    _attr_native_unit_of_measurement = "A"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        executor: WallboxClientExecutor,
        max_load: int,
    ) -> None:
        """Initialize the Wallbox max load number entity."""
        super().__init__(coordinator)
        self.executor = executor
        self._attr_unique_id = f"{executor.config_entry.entry_id}_max_current"
        self._attr_native_min_value = MIN_CURRENT
        self._attr_native_max_value = max_load
        self._attr_native_step = 1

    async def async_set_native_value(self, value: float) -> None:
        """Set the load limit to the given value."""
        _LOGGER.debug("Setting max current to %s A", value)
        try:
            await self.executor.call(
                "config_load_set", int(value), priority=1, timeout=15
            )
        except TimeoutError:
            _LOGGER.warning("config_load_set timed out; will refresh state anyway")
        except Exception as e:
            _LOGGER.error("config_load_set failed: %s", e)
            raise
        finally:
            await self.coordinator.async_request_refresh()

    @property
    def native_value(self) -> float | None:
        """Return the current load limit value."""
        value = self.executor.data.get("max_current")
        return float(value) if value is not None else None

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self.executor.last_update_success and "max_current" in self.executor.data
