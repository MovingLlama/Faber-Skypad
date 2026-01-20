"""Binary Sensor platform for Faber Skypad (Timer Status)."""
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
    """Adds the binary sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnActiveSensor(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnActiveSensor(BinarySensorEntity):
    """Indicates whether the timer is currently active."""

    _attr_translation_key = "timer_active"
    _attr_has_entity_name = True

    def __init__(self, name, entry_id, remote_entity, runtime_data):
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
        )

    @property
    def unique_id(self):
        return f"{self._entry_id}_run_on_active_sensor"

    @property
    def is_on(self):
        """Returns True if the timer is active."""
        return self._runtime_data.run_on_active

    @property
    def device_class(self):
        return BinarySensorDeviceClass.RUNNING

    @property
    def icon(self):
        return "mdi:timer-outline" if self.is_on else "mdi:timer-off-outline"

    async def async_added_to_hass(self):
        """Registers the listener for updates."""
        self._runtime_data.register_listener(self._handle_update)

    async def async_will_remove_from_hass(self):
        """Removes the listener."""
        self._runtime_data.unregister_listener(self._handle_update)

    @callback
    def _handle_update(self):
        """Is called when the runtime data changes."""
        self.async_write_ha_state()