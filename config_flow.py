"""Config flow für Faber Skypad."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_REMOTE_ENTITY, CONF_POWER_SENSOR

class FaberSkypadConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Faber Skypad."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Standard Installations-Schritt."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        # Das Formular Schema
        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default="Faber Küche"): str,
            vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "input_number"])
            ),
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )