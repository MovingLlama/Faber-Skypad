"""Config flow für die Faber Skypad Integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_REMOTE_ENTITY, CONF_POWER_SENSOR

class FaberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt den Konfigurationsablauf."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Der erste Schritt beim Hinzufügen der Integration."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Faber Skypad", data=user_input)

        # Definition des Formulars
        schema = vol.Schema({
            # Fernbedienung ist Pflicht
            vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            # Power Sensor ist jetzt OPTIONAL
            # Wir erlauben normale Sensoren (Watt) und Binary Sensoren (An/Aus Stecker)
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)