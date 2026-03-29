"""Button platform for Faber Skypad (Calibration & Status Correction)."""
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
        FaberCalibrationButton(name, config_entry.entry_id, remote_entity, runtime_data),
        FaberSyncFanButton(name, config_entry.entry_id, remote_entity, runtime_data),
        FaberSyncLightButton(name, config_entry.entry_id, remote_entity, runtime_data)
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

class FaberCalibrationButton(FaberBaseButton):
    """Button to start the calibration process."""
    
    _attr_translation_key = "start_calibration"

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        super().__init__(name, entry_id, remote_entity, runtime_data)
        self._attr_unique_id = f"{entry_id}_calibration_button"
        self._attr_icon = "mdi:auto-fix"

    async def async_press(self) -> None:
        """Executes the calibration process."""
        if self._runtime_data.fan_entity:
            await self._runtime_data.fan_entity.async_start_calibration()

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