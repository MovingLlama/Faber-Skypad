"""Number Plattform für Faber Skypad (Nachlaufzeit)."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_REMOTE_ENTITY, DEFAULT_RUN_ON_MINUTES

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt die Nummer-Eingabe hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnNumber(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnNumber(NumberEntity, RestoreEntity):
    """Eingabe für die Nachlaufzeit in Minuten."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._name = f"{name} Nachlaufzeit"
        self._base_name = name
        self._entry_id = entry_id
        self._remote_entity = remote_entity
        self._runtime_data = runtime_data
        self._value = DEFAULT_RUN_ON_MINUTES

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
        return f"{self._entry_id}_run_on_minutes"

    @property
    def native_value(self):
        return self._value

    @property
    def native_min_value(self):
        return 1

    @property
    def native_max_value(self):
        return 60

    @property
    def native_step(self):
        return 1
    
    @property
    def native_unit_of_measurement(self):
        return "min"

    @property
    def mode(self):
        return NumberMode.BOX

    async def async_added_to_hass(self):
        """Wiederherstellen des letzten Wertes."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
                self._runtime_data.run_on_minutes = int(self._value)
            except ValueError:
                self._value = DEFAULT_RUN_ON_MINUTES

    async def async_set_native_value(self, value: float) -> None:
        """Setzen des neuen Wertes."""
        self._value = value
        self._runtime_data.run_on_minutes = int(value)
        self.async_write_ha_state()