"""Integration for LRT Wallbox chargers."""

from datetime import timedelta
from functools import partial
import logging

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from lrt_wallbox import WallboxClient

from .config_flow import LrtWallboxOptionsFlow  # noqa: F401
from .const import DOMAIN, PLATFORMS, CONF_MAX_LOAD, ATTR_MAX_CURRENT, ATTR_ESP_FW, ATTR_ATMEL_FW, \
    ATTR_SETUP_STATUS_NETWORK, ATTR_SETUP_STATUS_AMBIENT_LIGHT, ATTR_SETUP_STATUS_MAX_CHARGING_POWER
from .helpers import WallboxClientExecutor, update_status
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_NAME, ATTR_SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME, default="LRT Wallbox"): vol.All(
                    cv.string, vol.Length(min=3, max=20)
                ),
                vol.Required(CONF_HOST): vol.All(
                    cv.string, vol.Length(min=7, max=15)
                ),
                vol.Required(CONF_USERNAME): vol.All(
                    cv.string, vol.Length(min=3, max=20)
                ),
                vol.Required(CONF_PASSWORD): vol.All(
                    cv.string, vol.Length(min=3, max=20)
                ),
                vol.Required(CONF_MAX_LOAD, default=16): vol.All(
                    cv.positive_int, vol.Range(min=6, max=32)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up LRT Wallbox from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = config_entry.data

    client = WallboxClient(
        ip=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
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
            ATTR_SERIAL_NUMBER: serial.serialNumber,
            ATTR_ESP_FW: f"{firmwares.esp['major']}.{firmwares.esp['minor']}.{firmwares.esp['patch']}",
            ATTR_ATMEL_FW: f"{firmwares.atmel['major']}.{firmwares.atmel['minor']}.{firmwares.atmel['revision']}.{firmwares.atmel['buildNumber']}",
            ATTR_SETUP_STATUS_NETWORK: not bool(setup_status.network),
            ATTR_SETUP_STATUS_AMBIENT_LIGHT: not bool(setup_status.ambientLight),
            ATTR_SETUP_STATUS_MAX_CHARGING_POWER: not bool(setup_status.maxChargingPower),
            ATTR_MAX_CURRENT: max_current.maxCurrent,
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
    if DOMAIN not in config:
        return True

    yaml_config = config[DOMAIN]

    existing_entry = hass.config_entries.async_entries(DOMAIN)
    if existing_entry:
        entry = existing_entry[0]
        hass.config_entries.async_update_entry(entry, data={
            CONF_NAME: yaml_config[CONF_NAME],
            CONF_HOST: yaml_config[CONF_HOST],
            CONF_USERNAME: yaml_config[CONF_USERNAME],
            CONF_PASSWORD: yaml_config[CONF_PASSWORD],
            CONF_MAX_LOAD: yaml_config[CONF_MAX_LOAD],
        })
        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.info("Updated existing %s config entry from YAML", DOMAIN)
        return True

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={
            CONF_NAME: yaml_config[CONF_NAME],
            CONF_HOST: yaml_config[CONF_HOST],
            CONF_USERNAME: yaml_config[CONF_USERNAME],
            CONF_PASSWORD: yaml_config[CONF_PASSWORD],
            CONF_MAX_LOAD: yaml_config[CONF_MAX_LOAD],
        })
    _LOGGER.info("Imported %s configuration from YAML", DOMAIN)
    return True


