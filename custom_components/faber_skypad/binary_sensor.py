"""Binary Sensor Plattform für Faber Skypad (Nachlauf Status)."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
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
    """Fügt den Binary Sensor hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnActiveSensor(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnActiveSensor(BinarySensorEntity):
    """Zeigt an, ob der Nachlauf gerade aktiv läuft."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._name = f"{name} Nachlauf Aktiv"
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
        return f"{self._entry_id}_run_on_active_sensor"

    @property
    def is_on(self):
        """Gibt True zurück, wenn der Nachlauf aktiv ist."""
        return self._runtime_data.run_on_active

    @property
    def device_class(self):
        return BinarySensorDeviceClass.RUNNING

    @property
    def icon(self):
        return "mdi:timer-outline" if self.is_on else "mdi:timer-off-outline"

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