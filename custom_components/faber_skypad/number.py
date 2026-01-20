"""Number platform for Faber Skypad (Timer Duration)."""
from homeassistant.components.number import NumberEntity, NumberMode
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
    """Adds the number entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberRunOnTimeNumber(name, remote_entity, config_entry.entry_id, runtime_data)])

class FaberRunOnTimeNumber(NumberEntity):
    """Setting for the timer duration in seconds."""

    _attr_translation_key = "timer_duration"
    _attr_has_entity_name = True

    def __init__(self, name, remote_entity, entry_id, runtime_data):
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
        return f"{self._entry_id}_run_on_time"

    @property
    def native_value(self):
        return self._runtime_data.run_on_seconds

    @property
    def native_min_value(self):
        return 10 # Minimum 10 seconds

    @property
    def native_max_value(self):
        return 3600 # Maximum 1 hour (3600 seconds)

    @property
    def native_step(self):
        return 5 # Steps of 5 seconds

    @property
    def mode(self):
        return NumberMode.BOX

    @property
    def native_unit_of_measurement(self):
        return "s" # Unit seconds

    @property
    def icon(self):
        return "mdi:timer-cog"

    async def async_set_native_value(self, value: float) -> None:
        self._runtime_data.run_on_seconds = int(value)
        self.async_write_ha_state()