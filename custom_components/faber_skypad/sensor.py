"""Sensor platform for Faber Skypad (Timer Countdown)."""
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
    """Adds the sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnTimeSensor(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnTimeSensor(SensorEntity):
    """Shows when the timer will end."""

    _attr_translation_key = "timer_end"
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
        return f"{self._entry_id}_run_on_end_time"

    @property
    def native_value(self):
        """Returns the end time."""
        return self._runtime_data.run_on_finish_time

    @property
    def device_class(self):
        """Timestamp provides the countdown display in the frontend."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        return "mdi:clock-end"

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