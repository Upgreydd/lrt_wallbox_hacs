"""Switch entity for Wallbox charging control."""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from lrt_wallbox import WallboxError

from .const import DOMAIN, ATTR_CHARGER_IS_CHARGING, ATTR_LAST_TRANSACTION_START_TIME, ATTR_LAST_TRANSACTION_END_TIME, \
    ATTR_LAST_TRANSACTION_ENERGY
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wallbox switch entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    executor: WallboxClientExecutor = data["executor"]
    coordinator: DataUpdateCoordinator = data["coordinator"]

    async_add_entities([WallboxChargeSwitch(coordinator, executor)])


class WallboxChargeSwitch(CoordinatorEntity, WallboxBaseEntity, SwitchEntity):
    """Switch to start/stop Wallbox charging."""

    _attr_has_entity_name = True
    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator, executor: WallboxClientExecutor):
        """Initialize the Wallbox charging switch."""
        super().__init__(coordinator)
        self.executor = executor
        self._attr_unique_id = f"{executor.config_entry.entry_id}_charging"

    async def async_turn_on(self, **kwargs) -> None:
        """Start charging."""
        _LOGGER.debug("Starting charging")
        first_tag = await self.executor.call("rfid_get", priority=1)
        await self.executor.call("transaction_start", first_tag[0].tagId, priority=1)
        self.executor.data[ATTR_CHARGER_IS_CHARGING] = False
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop charging."""
        _LOGGER.debug("Stopping charging")
        try:
            transaction_time = await self.executor.call("transaction_stop", priority=1)
            start_dt = datetime.strptime(
                transaction_time.startTime, "%Y-%m-%d %H:%M:%S %Z"
            ).replace(tzinfo=UTC)
            end_dt = datetime.strptime(
                transaction_time.endTime, "%Y-%m-%d %H:%M:%S %Z"
            ).replace(tzinfo=UTC)
            self.executor.data[ATTR_LAST_TRANSACTION_START_TIME] = start_dt
            self.executor.data[ATTR_LAST_TRANSACTION_END_TIME] = end_dt
            self.executor.data[ATTR_LAST_TRANSACTION_ENERGY] = round(
                transaction_time.energy / 1000, 2
            )  # Convert Wh to kWh

        except WallboxError as e:
            if e.kind == "NotFound":
                _LOGGER.warning("No active transaction found to stop")
        self.executor.data[ATTR_CHARGER_IS_CHARGING] = False
        await self.executor.save_persistent_data()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return True if charging is active."""
        return bool(self.executor.data.get(ATTR_CHARGER_IS_CHARGING, False))

    @property
    def available(self) -> bool:
        """Check if the switch is available."""
        return self.executor.last_update_success
