"""Integration for LRT Wallbox chargers."""

from datetime import timedelta
from functools import partial
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from lrt_wallbox import WallboxClient

from .config_flow import LrtWallboxOptionsFlow  # noqa: F401
from .const import DOMAIN, PLATFORMS
from .helpers import WallboxClientExecutor, update_status

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up LRT Wallbox from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = config_entry.data

    client = WallboxClient(
        ip=data["host"],
        username=data["username"],
        password=data["password"],
    )
    executor = WallboxClientExecutor(client, hass, config_entry)
    await executor.load_persistent_data()

    # One time initialization to fetch initial data
    serial = await executor.call("info_serial_get")
    firmwares = await executor.call("info_firmwares_get")
    setup_status = await executor.call("setup_get")
    max_current = await executor.call("config_load_get")

    executor.data.update(
        {
            "serial_number": serial.serialNumber,
            "esp_fw": f"{firmwares.esp['major']}.{firmwares.esp['minor']}.{firmwares.esp['patch']}",
            "atmel_fw": f"{firmwares.atmel['major']}.{firmwares.atmel['minor']}.{firmwares.atmel['revision']}.{firmwares.atmel['buildNumber']}",
            "setup_status_network": not bool(setup_status.network),
            "setup_status_ambientLight": not bool(setup_status.ambientLight),
            "setup_status_maxChargingPower": not bool(setup_status.maxChargingPower),
            "max_current": max_current.maxCurrent,
        }
    )

    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        config_entry=config_entry,
        name="LRT Wallbox Status",
        update_interval=timedelta(seconds=5),
        update_method=partial(update_status, executor),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await executor.shutdown()
        raise ConfigEntryNotReady(f"Wallbox not ready: {err}") from err

    hass.data[DOMAIN][config_entry.entry_id] = {
        "executor": executor,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].pop(config_entry.entry_id, None)

    if data:
        await data["executor"].shutdown()

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration via YAML (not supported)."""
    return True
