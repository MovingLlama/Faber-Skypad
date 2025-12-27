"""Number Plattform für Faber Skypad (Nachlauf Zeit)."""
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
    """Fügt die Number Entität hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberRunOnTimeNumber(name, remote_entity, config_entry.entry_id, runtime_data)])

class FaberRunOnTimeNumber(NumberEntity):
    """Einstellung für die Nachlaufzeit in Sekunden."""

    def __init__(self, name, remote_entity, entry_id, runtime_data):
        self._name = f"{name} Nachlaufzeit"
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
        return f"{self._entry_id}_run_on_time"

    @property
    def native_value(self):
        return self._runtime_data.run_on_seconds

    @property
    def native_min_value(self):
        return 10 # Minimum 10 Sekunden

    @property
    def native_max_value(self):
        return 3600 # Maximum 1 Stunde (3600 Sekunden)

    @property
    def native_step(self):
        return 5 # Schritte von 5 Sekunden

    @property
    def mode(self):
        return NumberMode.BOX

    @property
    def native_unit_of_measurement(self):
        return "s" # Einheit Sekunden

    @property
    def icon(self):
        return "mdi:timer-cog"

    async def async_set_native_value(self, value: float) -> None:
        self._runtime_data.run_on_seconds = int(value)
        self.async_write_ha_state()