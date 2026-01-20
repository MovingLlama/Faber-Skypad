"""Config flow for the Faber Skypad integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_REMOTE_ENTITY, CONF_POWER_SENSOR

_LOGGER = logging.getLogger(__name__)


class FaberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the configuration flow (initial setup)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """The first step when adding the integration."""
        errors = {}

        if user_input is not None:
            # Validation could be extended here
            return self.async_create_entry(title="Faber Skypad", data=user_input)

        # Definition of the form for the initial setup
        schema = vol.Schema({
            # Remote is mandatory
            vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            # Power Sensor is optional
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Defines the options flow handler for later changes."""
        return FaberOptionsFlowHandler(config_entry)


class FaberOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options (subsequent configuration via 'Configure')."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initializes the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Shows the form with the current values."""
        if user_input is not None:
            # The user_input contains the new options. We create an entry with this
            # data, and HA will store it in config_entry.options and reload the integration.
            return self.async_create_entry(title="", data=user_input)

        # When building the form, we show the current options, falling back to the
        # initial data if no options have been set yet.
        combined_config = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema({
            vol.Required(
                CONF_REMOTE_ENTITY,
                default=combined_config.get(CONF_REMOTE_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            vol.Optional(
                CONF_POWER_SENSOR,
                default=combined_config.get(CONF_POWER_SENSOR)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
