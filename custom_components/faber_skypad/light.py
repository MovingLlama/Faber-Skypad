"""Light Plattform für Faber Skypad."""
import logging
import asyncio

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CMD_LIGHT,
    DEFAULT_DELAY,
    CMD_HOLD_SECS,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt die Light Entität hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberLight(name, remote_entity, config_entry.entry_id)])

class FaberLight(LightEntity):
    """Repräsentation des Faber Skypad Lichts."""

    def __init__(self, name, remote_entity, entry_id):
        self._name = name
        self._remote_entity = remote_entity
        self._entry_id = entry_id
        self._is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer="Faber",
            model="Skypad",
            # via_device entfernt
        )

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._entry_id}_light"

    @property
    def is_on(self):
        return self._is_on

    @property
    def color_mode(self):
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        return {ColorMode.ONOFF}
    
    async def _send_command(self, command):
        """Sendet einen Befehl an die Remote."""
        if not command:
            _LOGGER.warning("Kein Befehl für Licht konfiguriert (CMD_LIGHT ist leer).")
            return

        cmd_formatted = command if command.startswith("b64:") else f"b64:{command}"
        
        _LOGGER.debug("Sende Licht-Befehl an %s: %s (Hold: %ss)", self._remote_entity, cmd_formatted, CMD_HOLD_SECS)

        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": [cmd_formatted],
                "hold_secs": CMD_HOLD_SECS,
            },
            blocking=True
        )
        await asyncio.sleep(DEFAULT_DELAY)

    async def async_turn_on(self, **kwargs):
        """Einschalten."""
        if not self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Ausschalten."""
        if self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = False
        self.async_write_ha_state()