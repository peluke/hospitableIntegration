"""Config flow for Hospitable API."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HospitableApiClient, HospitableApiError
from .const import CONF_LOOKAHEAD_DAYS, CONF_PROPERTY_UUIDS, DEFAULT_LOOKAHEAD_DAYS, DOMAIN


class HospitableConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hospitable API config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Set up Hospitable API from the UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = HospitableApiClient(
                session=async_get_clientsession(self.hass),
                api_token=user_input[CONF_API_TOKEN],
            )
            try:
                await api.async_validate_token()
            except HospitableApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id("hospitable_api")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Hospitable API", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Optional(CONF_PROPERTY_UUIDS, default=""): str,
                    vol.Optional(CONF_LOOKAHEAD_DAYS, default=DEFAULT_LOOKAHEAD_DAYS): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=365)
                    ),
                }
            ),
            errors=errors,
        )

