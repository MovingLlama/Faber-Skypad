"""Button Plattform für Faber Skypad (Kalibrierung)."""
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
    """Fügt den Button hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberCalibrationButton(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberCalibrationButton(ButtonEntity):
    """Button um den Lernlauf zu starten."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._attr_name = f"{name} Kalibrierung Starten"
        self._entry_id = entry_id
        self._remote_entity = remote_entity
        self._runtime_data = runtime_data
        self._attr_unique_id = f"{entry_id}_calibration_button"
        self._attr_icon = "mdi:auto-fix"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._runtime_data.fan_entity.name if self._runtime_data.fan_entity else "Faber Skypad",
            manufacturer="Faber",
            model="Skypad",
            # via_device entfernt
        )

    async def async_press(self) -> None:
        """Führt den Lernlauf aus."""
        if self._runtime_data.fan_entity:
            await self._runtime_data.fan_entity.async_start_calibration()