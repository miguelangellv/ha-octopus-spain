"""Config flow for Octopus Energy Spain."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .lib.octopus_spain import OctopusSpain

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(multiline=False, type=TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(multiline=False, type=TextSelectorType.PASSWORD)),
    }
)


class PlaceholderHub:  # pylint: disable=too-few-public-methods
    """Placeholder hub to hold user credentials."""

    def __init__(self, email: str, password: str) -> None:
        """Initialize."""
        self.email = email
        self.password = password


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Octopus Energy Spain."""

    VERSION = 1

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Return True if other_flow matches this flow."""
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=SCHEMA)

        api = OctopusSpain(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
        if await api.login():
            return self.async_create_entry(data=user_input, title="Octopus Spain")

        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors={"base": "invalid_auth"})


class OptionFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Octopus Energy Spain."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        email = self.config_entry.options.get(CONF_EMAIL, self.config_entry.data[CONF_EMAIL])
        password = self.config_entry.options.get(CONF_PASSWORD, self.config_entry.data[CONF_PASSWORD])

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=email): TextSelector(TextSelectorConfig(multiline=False, type=TextSelectorType.EMAIL)),
                vol.Required(CONF_PASSWORD, default=password): TextSelector(
                    TextSelectorConfig(multiline=False, type=TextSelectorType.PASSWORD)
                ),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)

        api = OctopusSpain(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
        if await api.login():
            return self.async_create_entry(data=user_input, title="Octopus Spain")

        return self.async_show_form(step_id="init", data_schema=SCHEMA, errors={"base": "invalid_auth"})
