"""Die Faber Skypad Komponente."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform

from .const import DOMAIN, DEFAULT_RUN_ON_MINUTES

_LOGGER = logging.getLogger(__name__)

# Wir fügen BINARY_SENSOR hinzu
PLATFORMS = [Platform.FAN, Platform.LIGHT, Platform.SWITCH, Platform.NUMBER, Platform.BINARY_SENSOR]

class FaberRuntimeData:
    """Klasse zum Speichern von Laufzeitdaten, die zwischen Entitäten geteilt werden."""
    def __init__(self):
        self.run_on_enabled = False
        self.run_on_minutes = DEFAULT_RUN_ON_MINUTES
        
        # NEU: Status für den aktiven Nachlauf und Listener
        self.run_on_active = False
        self._listeners = []

    def register_listener(self, callback_func):
        """Registriert eine Funktion, die bei Änderungen aufgerufen wird."""
        self._listeners.append(callback_func)
        
    def unregister_listener(self, callback_func):
        """Entfernt einen Listener."""
        if callback_func in self._listeners:
            self._listeners.remove(callback_func)

    def trigger_update(self):
        """Informiert alle Listener über Änderungen."""
        for callback_func in self._listeners:
            callback_func()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setzt die Integration aus der Konfiguration auf."""
    hass.data.setdefault(DOMAIN, {})
    
    # Wir speichern Config UND Runtime Data zusammen
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "runtime_data": FaberRuntimeData()
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok