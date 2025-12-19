"""Sensor Plattform für Faber Skypad (Nachlauf Countdown)."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_REMOTE_ENTITY

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt den Sensor hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnTimeSensor(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnTimeSensor(SensorEntity):
    """Zeigt an, wann der Nachlauf endet."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._name = f"{name} Nachlauf Ende"
        self._base_name = name
        self._entry_id = entry_id
        self._remote_entity = remote_entity
        self._runtime_data = runtime_data
        
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_name,
            manufacturer="Faber",
            model="Skypad",
            via_device=(DOMAIN, self._remote_entity),
        )

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._entry_id}_run_on_end_time"

    @property
    def native_value(self):
        """Gibt den Endzeitpunkt zurück."""
        return self._runtime_data.run_on_finish_time

    @property
    def device_class(self):
        """Timestamp sorgt für die Countdown-Anzeige im Frontend."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        return "mdi:clock-end"

    async def async_added_to_hass(self):
        """Registriert den Listener für Updates."""
        self._runtime_data.register_listener(self._handle_update)

    async def async_will_remove_from_hass(self):
        """Entfernt den Listener."""
        self._runtime_data.unregister_listener(self._handle_update)

    @callback
    def _handle_update(self):
        """Wird aufgerufen, wenn sich Runtime Data ändert."""
        self.async_write_ha_state()