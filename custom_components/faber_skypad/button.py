"""Button platform for Faber Skypad (Status Correction)."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CMD_TURN_ON_OFF,
    CMD_LIGHT,
    CMD_HOLD_SECS,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Adds the buttons."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([
        FaberSyncFanButton(name, config_entry.entry_id, remote_entity, runtime_data),
        FaberSyncLightButton(name, config_entry.entry_id, remote_entity, runtime_data),
        FaberResetCalibrationButton(name, config_entry.entry_id, remote_entity, runtime_data)
    ])

class FaberBaseButton(ButtonEntity):
    """Base class for Faber buttons."""

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

    async def _send_raw_command(self, command: str) -> None:
        """Sends a command to the remote without changing the internal state."""
        if not command:
            return
        cmd_formatted = command if command.startswith("b64:") else f"b64:{command}"
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": [cmd_formatted],
                "hold_secs": CMD_HOLD_SECS,
            },
        )

class FaberSyncFanButton(FaberBaseButton):
    """Button to manually synchronize the fan state (command only)."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        super().__init__(name, entry_id, remote_entity, runtime_data)
        self._attr_name = "Sync Fan"
        self._attr_unique_id = f"{entry_id}_sync_fan_button"
        self._attr_icon = "mdi:fan-alert"

    async def async_press(self) -> None:
        """Sends the fan command without changing the state."""
        await self._send_raw_command(CMD_TURN_ON_OFF)

class FaberSyncLightButton(FaberBaseButton):
    """Button to manually synchronize the light state (command only)."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        super().__init__(name, entry_id, remote_entity, runtime_data)
        self._attr_name = "Sync Light"
        self._attr_unique_id = f"{entry_id}_sync_light_button"
        self._attr_icon = "mdi:lightbulb-alert"

    async def async_press(self) -> None:
        """Sends the light command without changing the state."""
        await self._send_raw_command(CMD_LIGHT)


class FaberResetCalibrationButton(FaberBaseButton):
    """Button to reset the calibration data."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        super().__init__(name, entry_id, remote_entity, runtime_data)
        self._attr_name = "Reset Calibration"
        self._attr_unique_id = f"{entry_id}_reset_calibration_button"
        self._attr_icon = "mdi:restore"

    async def async_press(self) -> None:
        """Resets the power profile and last calibration in config entry."""
        if self._runtime_data.fan_entity:
            self._runtime_data.fan_entity._power_profile = {
                "off": 0.0,
                "light_on": 0.0,
                "fan_1": 0.0,
                "fan_2": 0.0,
                "fan_3": 0.0,
                "fan_boost": 0.0,
            }
        
        # Update config entry data
        new_data = {**self._runtime_data.config_entry.data}
        if "power_profile" in new_data:
            del new_data["power_profile"]
        if "last_calibration" in new_data:
            del new_data["last_calibration"]
            
        self.hass.config_entries.async_update_entry(
            self._runtime_data.config_entry, data=new_data
        )
        
        self._runtime_data.trigger_update()