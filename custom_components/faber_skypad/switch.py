"""Switch platform for Faber Skypad (Automatic Timer)."""
from homeassistant.components.switch import SwitchEntity
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
    """Adds the switch."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberRunOnSwitch(name, remote_entity, config_entry.entry_id, runtime_data)])

class FaberRunOnSwitch(SwitchEntity):
    """Switch to enable/disable the automatic timer."""

    _attr_translation_key = "automatic_timer"
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
        return f"{self._entry_id}_run_on_switch"

    @property
    def is_on(self):
        return self._runtime_data.run_on_enabled

    @property
    def icon(self):
        return "mdi:fan-clock"

    async def async_turn_on(self, **kwargs):
        self._runtime_data.run_on_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._runtime_data.run_on_enabled = False
        self.async_write_ha_state()