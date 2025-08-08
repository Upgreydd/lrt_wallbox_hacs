"""Base entity classes for the LRT Wallbox integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .helpers import WallboxClientExecutor


class WallboxBaseEntity(Entity):
    """Base class for all LRT Wallbox entities."""

    def __init__(self, executor: WallboxClientExecutor) -> None:
        """Initialize the base entity."""
        self.executor = executor

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for the Wallbox."""
        return DeviceInfo(
            identifiers={
                (self.executor.config_entry.domain, self.executor.config_entry.entry_id)
            },
            name="LRT Wallbox",
            manufacturer="LRT eMobility",
            model="Smart Vibe",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        key = getattr(self, "_key", None)
        return super().available and key is not None and key in self.executor.data
