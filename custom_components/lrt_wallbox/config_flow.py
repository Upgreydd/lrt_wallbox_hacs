"""Configuration flow for LRT Wallbox integration."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from lrt_wallbox import WallboxError
from .const import CONF_MAX_LOAD, DOMAIN
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_NAME
from .helpers import WallboxClientExecutor, tag_id_to_hex
from homeassistant.helpers import config_validation as cv


def general_data_schema(current=None):
    """Return a schema for general configuration data."""
    if current is None:
        current = {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=current.get(CONF_NAME, "LRT Wallbox")): vol.All(
                cv.string, vol.Length(min=3, max=20)
            ),
            vol.Required(CONF_HOST, default=current.get(CONF_HOST)): vol.All(
                cv.string, vol.Length(min=7, max=15)
            ),
            vol.Required(CONF_USERNAME, default=current.get(CONF_USERNAME)): vol.All(
                cv.string, vol.Length(min=3, max=20)
            ),
            vol.Required(CONF_PASSWORD, default=current.get(CONF_PASSWORD)): vol.All(
                cv.string, vol.Length(min=3, max=20)
            ),
            vol.Required(CONF_MAX_LOAD, default=current.get(CONF_MAX_LOAD, 16)): vol.All(
                cv.positive_int, vol.Range(min=6, max=32)
            ),
        }
    )


class LrtWallboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LRT Wallbox."""

    VERSION = 1

    DATA_SCHEMA = general_data_schema()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"LRT Wallbox @ {user_input[CONF_HOST]} (user: {user_input[CONF_USERNAME]})",
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_MAX_LOAD: user_input[CONF_MAX_LOAD],
                },
                options={},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.DATA_SCHEMA,
            errors={},
            description_placeholders={
                CONF_NAME: "Custom name for your wallbox",
                CONF_HOST: "IP address of your wallbox",
                CONF_USERNAME: "Username set while configuring wallbox over LRT PowerUP",
                CONF_PASSWORD: "Password received while configuring wallbox over LRT PowerUP",
                CONF_MAX_LOAD: "Max load (soft limiter) for your wallbox in Amper",
            },
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler for this config entry."""
        return LrtWallboxOptionsFlow(config_entry)


class LrtWallboxOptionsFlow(config_entries.OptionsFlow):
    """Options flow for LRT Wallbox integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry
        self.tag_id = None

    async def async_step_init(self, user_input=None):
        """Present the initial options step."""
        if user_input is not None:
            choice = user_input["choice"]
            if choice == "general":
                return await self.async_step_general()
            if choice == "rfid":
                return await self.async_step_start_scan()
            if choice == "rfid_delete":
                return await self.async_step_rfid_delete()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("choice"): vol.In(
                        {
                            "general": "Configure Wallbox connection",
                            "rfid": "Add RFID tag",
                            "rfid_delete": "Delete RFID tag",
                        }
                    )
                }
            ),
        )

    async def async_step_general(self, user_input=None):
        """Handle general settings update step."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_MAX_LOAD: user_input[CONF_MAX_LOAD],
                },
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="Updated settings", data={})

        return self.async_show_form(
            step_id="general",
            data_schema=general_data_schema(
                {**self.config_entry.data, **self.config_entry.options}
            ),
        )

    async def async_step_start_scan(self, user_input=None):
        """Start scanning for a new RFID tag."""
        executor: WallboxClientExecutor = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]["executor"]
        try:
            self.tag_id = await executor.call("rfid_scan")
        except WallboxError as e:
            return self.async_abort(reason=f"Error scanning RFID: {e.message}")
        return await self.async_step_enter_name()

    async def async_step_enter_name(self, user_input=None):
        """Prompt for a name for the new RFID tag."""
        if user_input is not None:
            executor: WallboxClientExecutor = self.hass.data[DOMAIN][
                self.config_entry.entry_id
            ]["executor"]
            try:
                await executor.call("rfid_add", self.tag_id, user_input["name"])
            except WallboxError as e:
                return self.async_abort(reason=f"Error adding RFID: {e.message}")
            return self.async_create_entry(
                title=f"RFID Tag '{user_input['name']}' added", data={}
            )

        return self.async_show_form(
            step_id="enter_name",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                }
            ),
        )

    async def async_step_rfid_delete(self, user_input=None):
        """Handle deletion of an RFID tag."""
        executor: WallboxClientExecutor = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]["executor"]

        try:
            rfid_tags = await executor.call("rfid_get")
        except WallboxError as e:
            return self.async_abort(reason=f"Error getting RFID tags: {e.message}")
        if not rfid_tags:
            return self.async_abort(reason="No RFID tags found")

        tag_choices = {
            tag_id_to_hex(tag.tagId): f"{tag_id_to_hex(tag.tagId)} - {tag.name}"
            for tag in rfid_tags
        }

        if user_input is not None:
            selected_tag_id_hex = user_input["tag_id"]
            selected_tag = next(
                (
                    tag
                    for tag in rfid_tags
                    if tag_id_to_hex(tag.tagId) == selected_tag_id_hex
                ),
                None,
            )

            if selected_tag is None:
                return self.async_abort(reason="Tag ID not found")

            try:
                await executor.call("rfid_delete", selected_tag.tagId)
            except WallboxError as e:
                return self.async_abort(reason=f"Error deleting RFID: {e.message}")

            return self.async_create_entry(
                title=f"RFID Tag '{selected_tag.name}' deleted", data={}
            )

        return self.async_show_form(
            step_id="rfid_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("tag_id"): vol.In(tag_choices),
                }
            ),
            description_placeholders={
                "warning": "Deleting an RFID tag will remove it permanently. Make sure you want to proceed."
            },
            last_step=True,
        )
