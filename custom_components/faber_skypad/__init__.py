"""Die Faber Skypad Komponente."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, DEFAULT_RUN_ON_SECONDS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.FAN, 
    Platform.LIGHT, 
    Platform.SWITCH, 
    Platform.NUMBER, 
    Platform.BINARY_SENSOR, 
    Platform.SENSOR, 
    Platform.BUTTON
]

class FaberRuntimeData:
    """Klasse zum Speichern von Laufzeitdaten, die zwischen Entitäten geteilt werden."""
    def __init__(self):
        self.run_on_enabled = False
        self.run_on_seconds = DEFAULT_RUN_ON_SECONDS
        self.run_on_active = False
        self.run_on_finish_time = None
        self.fan_entity = None
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
    
    _LOGGER.debug("Setup Faber Skypad Entry: %s", entry.entry_id)

    # Runtime Data initialisieren
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "runtime_data": FaberRuntimeData()
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Reload Listener registrieren, damit Änderungen in der Config sofort greifen
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Lädt die Integration neu, wenn sich Optionen ändern."""
    await hass.config_entries.async_reload(entry.entry_id)