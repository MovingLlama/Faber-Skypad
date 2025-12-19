"""Fan Plattform für Faber Skypad."""
import logging
import asyncio
from typing import Any, Optional, Dict
from datetime import timedelta # NEU

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util # NEU

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

SPEED_MAPPING = {
    1: 33,
    2: 66,
    3: 100
}

PRESET_BOOST = "BOOST"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Fügt die Fan Entität hinzu."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    config = data["config"]
    runtime_data = data["runtime_data"]
    
    remote_entity = config[CONF_REMOTE_ENTITY]
    power_sensor = config.get(CONF_POWER_SENSOR)
    name = config.get("name", "Faber Skypad")

    async_add_entities([FaberFan(hass, name, remote_entity, power_sensor, config_entry.entry_id, runtime_data)])


class FaberFan(FanEntity):
    """Repräsentation des Faber Skypad Lüfters."""

    def __init__(self, hass, name, remote_entity, power_sensor, entry_id, runtime_data):
        self.hass = hass
        self._name = name
        self._remote_entity = remote_entity
        self._power_sensor = power_sensor
        self._entry_id = entry_id
        self._runtime_data = runtime_data
        
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0
        
        self._run_on_cancel_fn = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer="Faber",
            model="Skypad",
            via_device=(DOMAIN, self._remote_entity),
        )

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._entry_id}_fan"

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

    @property
    def _run_on_active(self):
        return self._runtime_data.run_on_active

    @_run_on_active.setter
    def _run_on_active(self, value):
        if self._runtime_data.run_on_active != value:
            self._runtime_data.run_on_active = value
            # Wenn nicht aktiv, auch Zeit löschen
            if not value:
                self._runtime_data.run_on_finish_time = None
            self._runtime_data.trigger_update()
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "run_on_active": self._run_on_active
        }

    async def async_added_to_hass(self):
        if self._power_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._power_sensor], self._async_power_sensor_changed
                )
            )

    @callback
    def _async_power_sensor_changed(self, event):
        pass

    async def _send_command(self, command):
        cmd_formatted = command if command.startswith("b64:") else f"b64:{command}"
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": [cmd_formatted],
            },
        )
        await asyncio.sleep(DEFAULT_DELAY)

    def _cancel_run_on_timer(self):
        """Bricht den laufenden Timer ab, falls vorhanden."""
        if self._run_on_cancel_fn:
            self._run_on_cancel_fn()
            self._run_on_cancel_fn = None
        self._run_on_active = False
        # Zeit Reset wird durch den Setter von _run_on_active erledigt

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        self._cancel_run_on_timer()

        if not self._is_on:
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = True
            self._current_speed_step = 1
            self._percentage = SPEED_MAPPING[1]
        
        if percentage:
            await self.async_set_percentage(percentage)
        elif preset_mode:
            await self.async_set_preset_mode(preset_mode)
            
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Ausschalten mit intelligenter Nachlauf-Logik."""
        
        if (self._is_on and 
            self._runtime_data.run_on_enabled and 
            not self._run_on_active):
            
            _LOGGER.info("Nachlauf aktiviert. Schalte auf Stufe 1 für %s Minuten.", self._runtime_data.run_on_minutes)
            
            await self.async_set_percentage(33)
            
            # Timer berechnen
            delay = self._runtime_data.run_on_minutes * 60
            
            # NEU: Endzeit setzen für Sensor
            self._runtime_data.run_on_finish_time = dt_util.utcnow() + timedelta(seconds=delay)
            self._run_on_active = True # Triggered Update für Sensor
            self.async_write_ha_state()
            
            self._run_on_cancel_fn = async_call_later(
                self.hass, 
                delay, 
                self._async_execute_final_turn_off_callback
            )
            return

        await self._async_execute_final_turn_off()

    async def _async_execute_final_turn_off_callback(self, _now):
        await self._async_execute_final_turn_off()

    async def _async_execute_final_turn_off(self):
        self._cancel_run_on_timer()

        if self._is_on:
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = False
            self._percentage = 0
            self._current_speed_step = 0
            self._preset_mode = None
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
            
        if self._run_on_active and percentage != SPEED_MAPPING[1]:
             self._cancel_run_on_timer()

        if not self._is_on:
            await self.async_turn_on()

        target_step = 1
        if percentage > 33: target_step = 2
        if percentage > 66: target_step = 3

        current = self._current_speed_step
        diff = target_step - current

        if diff > 0:
            for _ in range(diff):
                await self._send_command(CMD_INCREASE)
        elif diff < 0:
            for _ in range(abs(diff)):
                await self._send_command(CMD_DECREASE)

        self._current_speed_step = target_step
        self._percentage = SPEED_MAPPING[target_step]
        self._preset_mode = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        self._cancel_run_on_timer()
        
        if preset_mode == PRESET_BOOST:
            if not self._is_on:
                await self.async_turn_on()
            
            await self._send_command(CMD_BOOST)
            self._preset_mode = PRESET_BOOST
            async_call_later(self.hass, 300, self._reset_boost_status)
        else:
            await self.async_set_percentage(self._percentage)

        self.async_write_ha_state()

    @callback
    def _reset_boost_status(self, _now):
        if self._preset_mode == PRESET_BOOST:
            self._preset_mode = None
            self.async_write_ha_state()