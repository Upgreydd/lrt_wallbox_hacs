"""Wallbox button entities."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WallboxBaseEntity
from .helpers import WallboxClientExecutor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Wallbox button entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    executor: WallboxClientExecutor = data["executor"]

    async_add_entities([RestartWallboxButton(executor)])


class RestartWallboxButton(WallboxBaseEntity, ButtonEntity):
    """Button to restart the Wallbox."""

    _attr_name = "Restart Wallbox"
    _attr_has_entity_name = True
    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, executor: WallboxClientExecutor):
        """Initialize the button."""
        super().__init__(executor)
        self._attr_unique_id = f"{executor.config_entry.entry_id}_restart_wallbox"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.executor.call("util_restart", priority=1)
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Failed to restart wallbox: %s", e)

    @property
    def available(self) -> bool:
        """Return True if the button is available."""
        return (
            self.executor.last_update_success and "serial_number" in self.executor.data
        )
