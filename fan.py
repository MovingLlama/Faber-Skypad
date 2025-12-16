"""Fan Plattform für Faber Skypad."""
import logging
import asyncio
from typing import Any, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_ON, STATE_OFF

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_POWER_SENSOR,
    CMD_TURN_ON_OFF,
    CMD_INCREASE,
    CMD_DECREASE,
    CMD_BOOST,
    DEFAULT_DELAY
)

_LOGGER = logging.getLogger(__name__)

# Mapping von Stufen zu Prozent
SPEED_MAPPING = {
    1: 33,
    2: 66,
    3: 100
}

PRESET_BOOST = "boost"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt die Fan Entität hinzu."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    remote_entity = config[CONF_REMOTE_ENTITY]
    power_sensor = config.get(CONF_POWER_SENSOR)
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberFan(hass, name, remote_entity, power_sensor)])


class FaberFan(FanEntity):
    """Repräsentation des Faber Skypad Lüfters."""

    def __init__(self, hass, name, remote_entity, power_sensor):
        self.hass = hass
        self._name = name
        self._remote_entity = remote_entity
        self._power_sensor = power_sensor
        
        # Interner Status
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0 # 0, 1, 2, 3

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"faber_skypad_fan_{self._remote_entity}"

    @property
    def supported_features(self):
        return FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF | FanEntityFeature.PRESET_MODE

    @property
    def is_on(self):
        return self._is_on

    @property
    def percentage(self):
        return self._percentage

    @property
    def preset_mode(self):
        return self._preset_mode

    @property
    def preset_modes(self):
        return [PRESET_BOOST]

    async def async_added_to_hass(self):
        """Wird aufgerufen, wenn die Entity geladen wird."""
        # Hier abonnieren wir den Power Sensor für zukünftige Updates
        if self._power_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._power_sensor], self._async_power_sensor_changed
                )
            )

    @callback
    def _async_power_sensor_changed(self, event):
        """
        ZUKÜNFTIGE LOGIK: Hier werden die Watt-Werte ausgewertet.
        Beispiel (Pseudo-Code):
        
        watt = float(event.data.get("new_state").state)
        if watt < 5:
            self._is_on = False
            self._current_speed_step = 0
        elif watt < 50:
             self._current_speed_step = 1
             self._is_on = True
        ... usw.
        
        self.async_write_ha_state()
        """
        pass

    async def _send_command(self, command):
        """Hilfsfunktion zum Senden der IR Codes."""
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": command,
            },
        )
        # Kurze Pause damit das Gerät mitkommt
        await asyncio.sleep(DEFAULT_DELAY)

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Lüfter einschalten."""
        if not self._is_on:
            # Laut Beschreibung: Einschalten startet immer auf Stufe 1
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = True
            self._current_speed_step = 1
            self._percentage = SPEED_MAPPING[1]
        
        # Wenn direkt eine Geschwindigkeit oder Boost angefordert wurde
        if percentage:
            await self.async_set_percentage(percentage)
        elif preset_mode:
            await self.async_set_preset_mode(preset_mode)
            
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Lüfter ausschalten."""
        if self._is_on:
            # Ein/Aus Toggle
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = False
            self._percentage = 0
            self._current_speed_step = 0
            self._preset_mode = None
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Geschwindigkeit setzen (1-3)."""
        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._is_on:
            await self.async_turn_on()

        # Ziel-Stufe berechnen (1, 2 oder 3)
        target_step = 1
        if percentage > 33: target_step = 2
        if percentage > 66: target_step = 3

        # Differenz berechnen
        current = self._current_speed_step
        diff = target_step - current

        if diff == 0:
            # Nichts zu tun (außer wir kommen vom Boost zurück)
            if self._preset_mode == PRESET_BOOST:
                # Logik: Wenn wir im Boost sind, und jemand drückt manuell die alte Stufe,
                # gehen wir davon aus, dass wir Boost beenden wollen?
                # Da wir nicht wissen wie man Boost "abbricht" außer warten, 
                # senden wir hier nichts, sondern setzen nur den Status zurück.
                pass
            pass
        
        elif diff > 0:
            # Stärker drücken (diff mal)
            for _ in range(diff):
                await self._send_command(CMD_INCREASE)
        
        elif diff < 0:
            # Schwächer drücken (abs(diff) mal)
            for _ in range(abs(diff)):
                await self._send_command(CMD_DECREASE)

        self._current_speed_step = target_step
        self._percentage = SPEED_MAPPING[target_step]
        self._preset_mode = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Boost Modus setzen."""
        if preset_mode == PRESET_BOOST:
            if not self._is_on:
                await self.async_turn_on()
            
            await self._send_command(CMD_BOOST)
            self._preset_mode = PRESET_BOOST
            # Da wir die Geschwindigkeit im Boost nicht exakt kennen (vermutlich max), 
            # lassen wir percentage so wie es war oder setzen es auf 100, 
            # aber visuell ist 'Boost' dominant.
            
            # Timer Logik (Optional):
            # Da das Gerät nach wenigen Minuten zurückschaltet, müsste HA das eigentlich auch tun.
            # Hier simulieren wir das nach 5 Minuten (300 sekunden), 
            # um den Status in der UI wieder zu korrigieren.
            self.hass.loop.call_later(300, self._reset_boost_status)
        else:
            # Boost verlassen? Wir schalten einfach auf die gespeicherte Stufe zurück
            await self.async_set_percentage(self._percentage)

        self.async_write_ha_state()

    def _reset_boost_status(self):
        """Callback um Boost Status in der UI zu entfernen nach Zeitablauf."""
        if self._preset_mode == PRESET_BOOST:
            self._preset_mode = None
            self.async_write_ha_state()