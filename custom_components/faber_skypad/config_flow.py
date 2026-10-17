"""Config flow for the Faber Skypad integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_POWER_SENSOR,
    CONF_SYNC_DELAY,
    COMMAND_SETTLE_TIME,
    SYNC_DELAY_MAX,
)

_LOGGER = logging.getLogger(__name__)


class FaberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the configuration flow (initial setup)."""

    VERSION = 2

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
        return FaberOptionsFlowHandler()


class FaberOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options (subsequent configuration via 'Configure')."""

    async def async_step_init(self, user_input=None):
        """Shows the form with the current values."""
        if user_input is not None:
            # The platforms read their settings from config_entry.data, so the new
            # values are written there. Leftover options from older versions are
            # cleared; the data update triggers the reload of the integration.
            new_data = {**self.config_entry.data, **self.config_entry.options}
            new_data[CONF_REMOTE_ENTITY] = user_input[CONF_REMOTE_ENTITY]
            if user_input.get(CONF_POWER_SENSOR):
                new_data[CONF_POWER_SENSOR] = user_input[CONF_POWER_SENSOR]
            else:
                new_data.pop(CONF_POWER_SENSOR, None)
            new_data[CONF_SYNC_DELAY] = user_input.get(CONF_SYNC_DELAY, COMMAND_SETTLE_TIME)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data, options={}
            )
            return self.async_create_entry(title="", data={})

        # Show the current values, including options saved by older versions.
        combined_config = {**self.config_entry.data, **self.config_entry.options}

        # suggested_value instead of default, so the optional power sensor can be cleared
        schema = vol.Schema({
            vol.Required(
                CONF_REMOTE_ENTITY,
                description={"suggested_value": combined_config.get(CONF_REMOTE_ENTITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            vol.Optional(
                CONF_POWER_SENSOR,
                description={"suggested_value": combined_config.get(CONF_POWER_SENSOR)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
            # Time after own commands before the power sensor may correct the state
            vol.Optional(
                CONF_SYNC_DELAY,
                default=combined_config.get(CONF_SYNC_DELAY, COMMAND_SETTLE_TIME),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=SYNC_DELAY_MAX,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
