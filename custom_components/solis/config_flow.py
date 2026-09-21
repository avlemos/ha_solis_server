"""Config flow for Solis Client integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_TCP_PORT

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PORT, default=DEFAULT_TCP_PORT): vol.All(int, vol.Range(min=1, max=65535))
    }
)


class SolisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis Client."""

    VERSION = 1
    # 2: corrected the misspelled unique_id of the cumulative production sensor
    MINOR_VERSION = 2

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        # create entry, store port in options so it can be changed later
        return self.async_create_entry(title="Solis Client", data={}, options={CONF_PORT: int(user_input[CONF_PORT])})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SolisOptionsFlowHandler(config_entry)


class SolisOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Solis Client."""

    def __init__(self, config_entry):
        # do NOT assign to self.config_entry (read-only). Keep a private reference.
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        current = self._config_entry.options.get(CONF_PORT, DEFAULT_TCP_PORT)
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {vol.Required(CONF_PORT, default=current): vol.All(int, vol.Range(min=1, max=65535))}
                ),
            )

        return self.async_create_entry(title="", data={CONF_PORT: int(user_input[CONF_PORT])})