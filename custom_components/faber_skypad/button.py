"""Button platform for Faber Skypad (Calibration)."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_REMOTE_ENTITY

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Adds the button."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberCalibrationButton(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberCalibrationButton(ButtonEntity):
    """Button to start the calibration process."""
    
    _attr_translation_key = "start_calibration"
    _attr_has_entity_name = True

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._base_name = name
        self._entry_id = entry_id
        self._remote_entity = remote_entity
        self._runtime_data = runtime_data
        self._attr_unique_id = f"{entry_id}_calibration_button"
        self._attr_icon = "mdi:auto-fix"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_name,
            manufacturer="Faber",
            model="Skypad",
        )

    async def async_press(self) -> None:
        """Executes the calibration process."""
        if self._runtime_data.fan_entity:
            await self._runtime_data.fan_entity.async_start_calibration()