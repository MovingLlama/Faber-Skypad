"""Config flow für die Faber Skypad Integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
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
            # Power Sensor ist jetzt OPTIONAL und erlaubt auch binary_sensor
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Definiert den Options Flow Handler."""
        return FaberOptionsFlowHandler(config_entry)


class FaberOptionsFlowHandler(config_entries.OptionsFlow):
    """Handhabt die Optionen (nachträgliche Konfiguration)."""

    def __init__(self, config_entry):
        """Initialisiert den Options Flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Zeigt das Formular mit den aktuellen Werten an."""
        if user_input is not None:
            # Bestehende Daten kopieren, um nichts zu löschen
            new_data = self.config_entry.data.copy()
            
            # Remote Entity aktualisieren
            if CONF_REMOTE_ENTITY in user_input:
                new_data[CONF_REMOTE_ENTITY] = user_input[CONF_REMOTE_ENTITY]
            
            # Power Sensor aktualisieren
            # Wenn der Nutzer nichts auswählt (None/Leer), setzen wir es auf None
            if user_input.get(CONF_POWER_SENSOR):
                new_data[CONF_POWER_SENSOR] = user_input[CONF_POWER_SENSOR]
            else:
                new_data[CONF_POWER_SENSOR] = None

            # Wir aktualisieren die Config Entry Daten direkt
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            
            # Integration neu laden, um Änderungen sofort anzuwenden
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            return self.async_create_entry(title="", data={})

        # Aktuelle Werte aus der Konfiguration laden
        # .get() liefert None zurück, wenn der Schlüssel fehlt -> Sicher
        current_remote = self.config_entry.data.get(CONF_REMOTE_ENTITY)
        current_power = self.config_entry.data.get(CONF_POWER_SENSOR)

        # Schema dynamisch bauen
        fields = {}

        # 1. Remote Entity (Pflichtfeld)
        if current_remote:
            fields[vol.Required(CONF_REMOTE_ENTITY, default=current_remote)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            )
        else:
            fields[vol.Required(CONF_REMOTE_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            )

        # 2. Power Sensor (Optional)
        # WICHTIG: Wir prüfen explizit auf None, um Abstürze zu vermeiden
        if current_power is not None:
            fields[vol.Optional(CONF_POWER_SENSOR, default=current_power)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            )
        else:
            # Kein Standardwert, wenn bisher keiner gesetzt war (oder er None ist)
            fields[vol.Optional(CONF_POWER_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))