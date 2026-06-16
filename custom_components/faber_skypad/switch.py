"""Switch platform for Faber Skypad (Automatic Timer & Calibration Switch)."""
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
    """Adds the switches."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([
        FaberRunOnSwitch(name, remote_entity, config_entry.entry_id, runtime_data),
        FaberCalibrationSwitch(name, config_entry.entry_id, remote_entity, runtime_data)
    ])

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

class FaberCalibrationSwitch(SwitchEntity):
    """Switch to start/stop/cancel the calibration process."""

    _attr_translation_key = "calibration"
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
        return f"{self._entry_id}_calibration_switch"

    @property
    def is_on(self):
        """Returns True if calibration is running."""
        if self._runtime_data.fan_entity:
            return self._runtime_data.fan_entity._is_calibrating
        return False

    @property
    def icon(self):
        return "mdi:auto-fix"

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

    async def async_turn_on(self, **kwargs):
        """Starts calibration."""
        if self._runtime_data.fan_entity:
            await self._runtime_data.fan_entity.async_start_calibration()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Cancels calibration."""
        if self._runtime_data.fan_entity:
            await self._runtime_data.fan_entity.async_cancel_calibration()
        self.async_write_ha_state()