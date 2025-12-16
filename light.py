"""Licht Plattform für Faber Skypad."""
import logging
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CMD_LIGHT
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt die Light Entität hinzu."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberLight(name, remote_entity, hass)])


class FaberLight(LightEntity):
    """Repräsentation des Faber Skypad Lichts."""

    def __init__(self, name, remote_entity, hass):
        self._name = f"{name} Licht"
        self._remote_entity = remote_entity
        self.hass = hass
        self._is_on = False # Wir raten den Status, bis wir Power Metering haben

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"faber_skypad_light_{self._remote_entity}"

    @property
    def is_on(self):
        return self._is_on
    
    @property
    def color_mode(self):
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        return {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs):
        """Licht an."""
        if not self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Licht aus."""
        if self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = False
            self.async_write_ha_state()

    async def _send_command(self, command):
        """Sende IR Befehl."""
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": command,
            },
        )