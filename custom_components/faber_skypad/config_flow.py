"""Config flow für die Faber Skypad Integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_REMOTE_ENTITY, CONF_POWER_SENSOR

_LOGGER = logging.getLogger(__name__)

class FaberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt den Konfigurationsablauf (Ersteinrichtung)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Der erste Schritt beim Hinzufügen der Integration."""
        errors = {}
        
        if user_input is not None:
            # Validierung könnte hier erweitert werden
            return self.async_create_entry(title="Faber Skypad", data=user_input)

        # Definition des Formulars für die Ersteinrichtung
        schema = vol.Schema({
            # Remote ist Pflicht
            vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            ),
            # Power Sensor ist Optional
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
            ),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Definiert den Options Flow Handler für spätere Änderungen."""
        return FaberOptionsFlowHandler(config_entry)


class FaberOptionsFlowHandler(config_entries.OptionsFlow):
    """Handhabt die Optionen (nachträgliche Konfiguration via 'Konfigurieren')."""

    def __init__(self, config_entry):
        """Initialisiert den Options Flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Zeigt das Formular mit den aktuellen Werten an."""
        errors = {}

        if user_input is not None:
            # Wir kopieren die bestehenden Daten, um nichts versehentlich zu löschen
            new_data = self.config_entry.data.copy()
            
            # 1. Remote Entity Update
            if user_input.get(CONF_REMOTE_ENTITY):
                new_data[CONF_REMOTE_ENTITY] = user_input[CONF_REMOTE_ENTITY]
            
            # 2. Power Sensor Update
            # Wenn der Nutzer das Feld leer lässt (Löschen) oder ändert
            power_sensor_input = user_input.get(CONF_POWER_SENSOR)
            
            if power_sensor_input:
                new_data[CONF_POWER_SENSOR] = power_sensor_input
            else:
                # Explizites Löschen, wenn Feld leer
                new_data[CONF_POWER_SENSOR] = None

            # Daten in der Config Entry speichern
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            
            # Integration neu laden, damit Änderungen sofort wirksam werden
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            # Options Flow beenden
            return self.async_create_entry(title="", data={})

        # --- Formular Aufbauen ---
        
        # Aktuelle Werte sicher laden (.get verhindert Absturz bei fehlendem Key)
        current_remote = self.config_entry.data.get(CONF_REMOTE_ENTITY)
        current_power = self.config_entry.data.get(CONF_POWER_SENSOR)

        schema_fields = {}

        # 1. Remote Entity (Pflichtfeld)
        # Wir prüfen, ob ein alter Wert existiert und gültig (String) ist
        if current_remote and isinstance(current_remote, str):
            schema_fields[vol.Required(CONF_REMOTE_ENTITY, default=current_remote)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            )
        else:
            # Fallback: Kein Default, wenn Daten korrupt waren
            schema_fields[vol.Required(CONF_REMOTE_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="remote")
            )

        # 2. Power Sensor (Optional)
        power_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "binary_sensor"])
        )

        # Wir setzen den Default nur, wenn wirklich ein Entity-ID String da ist.
        # Leere Listen, None oder falsche Typen werden ignoriert.
        if current_power and isinstance(current_power, str):
            schema_fields[vol.Optional(CONF_POWER_SENSOR, default=current_power)] = power_selector
        else:
            # Feld leer anzeigen
            schema_fields[vol.Optional(CONF_POWER_SENSOR)] = power_selector

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_fields), errors=errors)