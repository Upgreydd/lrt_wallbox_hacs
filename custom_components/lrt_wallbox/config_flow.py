"""Configuration flow for LRT Wallbox integration."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_NAME

from lrt_wallbox import WallboxError

from .const import CONF_MAX_LOAD, DOMAIN
from .helpers import WallboxClientExecutor, tag_id_to_hex


def general_data_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Return a schema for general configuration data.

    Field labels come from translations:
      - config.step.user.data.*
      - config.step.general.data.*
    """
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
        """Handle the initial step of the config flow.

        Title/description/labels are taken from translations:
          config.step.user.title / description / data.*
        """
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
        self.tag_id: list[int] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Present the initial options step.

        Title/description/labels from translations:
          config.step.init.title / description / data.choice
        """
        if user_input is not None:
            choice = user_input["choice"]
            if choice == "general":
                return await self.async_step_general()
            if choice == "rfid":
                return await self.async_step_start_scan()
            if choice == "rfid_delete":
                return await self.async_step_rfid_delete()

        # Keep raw option keys; the field label is translated.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("choice"): vol.In(
                        {
                            "general": "general",
                            "rfid": "rfid",
                            "rfid_delete": "rfid_delete",
                        }
                    )
                }
            ),
        )

    async def async_step_general(self, user_input: dict[str, Any] | None = None):
        """Handle general settings update step.

        Title/description/labels from translations:
          config.step.general.title / description / data.*
        """
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

    async def async_step_start_scan(self, user_input: dict[str, Any] | None = None):
        """Start scanning for a new RFID tag.

        Abort reasons & placeholders from translations:
          config.abort.rfid_scan_failed
        """
        executor: WallboxClientExecutor = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]["executor"]
        try:
            self.tag_id = await executor.call("rfid_scan")
        except WallboxError as e:
            return self.async_abort(
                reason="rfid_scan_failed",
                description_placeholders={"error": e.message},
            )
        return await self.async_step_enter_name()

    async def async_step_enter_name(self, user_input: dict[str, Any] | None = None):
        """Prompt for a name for the new RFID tag.

        Title/labels from translations:
          config.step.enter_name.title / data.name
          Abort reasons:
          - config.abort.rfid_add_failed
        """
        if user_input is not None:
            executor: WallboxClientExecutor = self.hass.data[DOMAIN][
                self.config_entry.entry_id
            ]["executor"]
            try:
                await executor.call("rfid_add", self.tag_id, user_input["name"])
            except WallboxError as e:
                return self.async_abort(
                    reason="rfid_add_failed",
                    description_placeholders={"error": e.message},
                )
            return self.async_create_entry(title="RFID tag added", data={})

        return self.async_show_form(
            step_id="enter_name",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                }
            ),
        )

    async def async_step_rfid_delete(self, user_input: dict[str, Any] | None = None):
        """Handle deletion of an RFID tag.

        Title/description/labels from translations:
          config.step.rfid_delete.title / description / data.tag_id
          Abort reasons:
          - config.abort.rfid_delete_failed
          - config.abort.rfid_empty
          - config.abort.rfid_not_found
        """
        executor: WallboxClientExecutor = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]["executor"]

        try:
            rfid_tags = await executor.call("rfid_get")
        except WallboxError as e:
            return self.async_abort(
                reason="rfid_delete_failed",
                description_placeholders={"error": e.message},
            )
        if not rfid_tags:
            return self.async_abort(reason="rfid_empty")

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
                return self.async_abort(reason="rfid_not_found")

            try:
                await executor.call("rfid_delete", selected_tag.tagId)
            except WallboxError as e:
                return self.async_abort(
                    reason="rfid_delete_failed",
                    description_placeholders={"error": e.message},
                )

            return self.async_create_entry(title="RFID tag deleted", data={})

        return self.async_show_form(
            step_id="rfid_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("tag_id"): vol.In(tag_choices),
                }
            ),
            last_step=True,
        )
