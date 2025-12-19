"""Die Faber Skypad Komponente."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, DEFAULT_RUN_ON_MINUTES

_LOGGER = logging.getLogger(__name__)

# Wir fügen SWITCH und NUMBER hinzu
PLATFORMS = [Platform.FAN, Platform.LIGHT, Platform.SWITCH, Platform.NUMBER]

class FaberRuntimeData:
    """Klasse zum Speichern von Laufzeitdaten, die zwischen Entitäten geteilt werden."""
    def __init__(self):
        self.run_on_enabled = False
        self.run_on_minutes = DEFAULT_RUN_ON_MINUTES

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