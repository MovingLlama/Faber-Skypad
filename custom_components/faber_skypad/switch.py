"""Switch Plattform für Faber Skypad (Nachlauf Ein/Aus)."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_REMOTE_ENTITY

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt den Nachlauf-Schalter hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    name = config.get("name", "Faber Skypad")
    remote_entity = config[CONF_REMOTE_ENTITY]

    async_add_entities([FaberRunOnSwitch(name, config_entry.entry_id, remote_entity, runtime_data)])

class FaberRunOnSwitch(SwitchEntity, RestoreEntity):
    """Schalter zum Aktivieren des Nachlaufs."""

    def __init__(self, name, entry_id, remote_entity, runtime_data):
        self._name = f"{name} Nachlauf"
        self._base_name = name
        self._entry_id = entry_id
        self._remote_entity = remote_entity
        self._runtime_data = runtime_data
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Verknüpfung zum Hauptgerät."""
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
        return f"{self._entry_id}_run_on_switch"

    @property
    def is_on(self):
        return self._is_on

    async def async_added_to_hass(self):
        """Wiederherstellen des letzten Zustands nach Neustart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._is_on = last_state.state == "on"
            # Synchronisiere die Runtime Data
            self._runtime_data.run_on_enabled = self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        self._runtime_data.run_on_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        self._runtime_data.run_on_enabled = False
        self.async_write_ha_state()