"""Fan Plattform für Faber Skypad."""
import logging
import asyncio
from typing import Any, Optional, Dict
from datetime import timedelta

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_ON, STATE_OFF

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_POWER_SENSOR,
    CMD_TURN_ON_OFF,
    CMD_INCREASE,
    CMD_DECREASE,
    CMD_BOOST,
    DEFAULT_DELAY,
    CMD_HOLD_SECS,
    SPEED_MAPPING,
    PRESET_BOOST,
    CALIBRATION_WAIT_TIME,
    MATCH_TOLERANCE,
    FALLBACK_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

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

    fan = FaberFan(hass, name, remote_entity, power_sensor, config_entry.entry_id, runtime_data)
    # Fan in Runtime Data registrieren für Button Zugriff
    runtime_data.fan_entity = fan
    
    async_add_entities([fan])


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
        
        # Kalibrierungs-Daten
        self._is_calibrating = False
        self._calibration_step_cancel = None
        self._power_profile = {
            "off": 0.0,
            1: 0.0,
            2: 0.0,
            3: 0.0,
            "boost": 0.0
        }

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
            if not value:
                self._runtime_data.run_on_finish_time = None
            self._runtime_data.trigger_update()
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        attrs = {
            "run_on_active": self._run_on_active,
            "calibration_mode": self._is_calibrating
        }
        if self._power_sensor:
            # Zeige die gelernten Werte im GUI
            attrs["power_profile_off"] = f"{self._power_profile.get('off', 0):.1f} W"
            attrs["power_profile_1"] = f"{self._power_profile.get(1, 0):.1f} W"
            attrs["power_profile_2"] = f"{self._power_profile.get(2, 0):.1f} W"
            attrs["power_profile_3"] = f"{self._power_profile.get(3, 0):.1f} W"
            attrs["power_profile_boost"] = f"{self._power_profile.get('boost', 0):.1f} W"
        return attrs

    async def async_added_to_hass(self):
        if self._power_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._power_sensor], self._async_power_sensor_changed
                )
            )
            # Versuche existierende Werte zu laden (Fallback)
            state = self.hass.states.get(self._power_sensor)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._power_profile["off"] = float(state.state)
                except ValueError:
                    pass

    # --- POWER SENSOR LOGIK ---

    @callback
    def _async_power_sensor_changed(self, event):
        """Erkennt den Status anhand der gelernten Profile."""
        if self._is_calibrating:
            return

        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        try:
            current_power = float(new_state.state)
        except ValueError:
            # Fallback für binäre Sensoren
            if new_state.state == STATE_ON:
                self._update_state_from_binary(True)
            elif new_state.state == STATE_OFF:
                self._update_state_from_binary(False)
            return

        # Profil-Matching
        best_match = None
        min_diff = float("inf")

        for mode, profile_watt in self._power_profile.items():
            if profile_watt == 0 and mode != "off": continue
            
            diff = abs(current_power - profile_watt)
            if diff < min_diff:
                min_diff = diff
                best_match = mode

        # Entscheidung treffen
        detected_on = False
        detected_speed = 0
        detected_preset = None

        # Fallback Logik wenn keine Kalibrierung
        if self._power_profile[1] == 0:
            threshold = self._power_profile["off"] + FALLBACK_THRESHOLD
            if current_power > threshold:
                best_match = 1
            else:
                best_match = "off"

        # Auswerten
        if best_match == "off":
            detected_on = False
        elif best_match == "boost":
            detected_on = True
            detected_preset = PRESET_BOOST
            detected_speed = 3
        else: # 1, 2, 3
            detected_on = True
            detected_speed = best_match

        # Spezialfall Nachlauf: Wenn Nachlauf aktiv, nicht auf "An" synchen
        if self._run_on_active:
             if not detected_on:
                 self._cancel_run_on_timer()
                 self._is_on = False
                 self.async_write_ha_state()
             return

        # Synchronisierung
        if min_diff <= MATCH_TOLERANCE or (best_match == "off") or (self._power_profile[1] == 0):
            if detected_on != self._is_on or (detected_on and (detected_speed != self._current_speed_step or detected_preset != self._preset_mode)):
                _LOGGER.debug(f"Sync: Erkannt={best_match} ({current_power}W), Diff={min_diff:.1f}")
                
                self._is_on = detected_on
                if not detected_on:
                    self._percentage = 0
                    self._current_speed_step = 0
                    self._preset_mode = None
                else:
                    self._preset_mode = detected_preset
                    if detected_preset == PRESET_BOOST:
                         self._percentage = 100
                         self._current_speed_step = 3
                    else:
                        self._current_speed_step = detected_speed
                        self._percentage = SPEED_MAPPING[detected_speed]

                self.async_write_ha_state()

    def _update_state_from_binary(self, is_running):
        """Einfaches Update für Binary Sensoren ohne Watt-Messung."""
        if self._run_on_active:
             if not is_running:
                 self._cancel_run_on_timer()
                 self._is_on = False
                 self.async_write_ha_state()
             return

        if is_running != self._is_on:
            self._is_on = is_running
            if is_running:
                if self._percentage == 0:
                    self._percentage = SPEED_MAPPING[1]
                    self._current_speed_step = 1
            else:
                self._percentage = 0
                self._current_speed_step = 0
                self._preset_mode = None
            self.async_write_ha_state()

    # --- KALIBRIERUNG LOGIK ---

    async def async_start_calibration(self):
        """Startet den automatischen Lernlauf."""
        if self._is_calibrating:
            _LOGGER.warning("Kalibrierung läuft bereits.")
            return

        _LOGGER.info("Starte Faber Skypad Kalibrierung...")
        self._is_calibrating = True
        self.async_write_ha_state()

        # Start: Ausschalten um Baseline zu finden
        await self._send_command_raw(CMD_TURN_ON_OFF)
        self._calibration_step_cancel = async_call_later(self.hass, 6.0, self._calib_step_0_measure_off)

    async def _calib_step_0_measure_off(self, _now):
        val = self._get_current_power()
        self._power_profile["off"] = val
        _LOGGER.info(f"Kalibrierung: Baseline (Off) = {val} W")
        
        await self._send_command_raw(CMD_TURN_ON_OFF)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_1_measure)

    async def _calib_step_1_measure(self, _now):
        val = self._get_current_power()
        self._power_profile[1] = val
        _LOGGER.info(f"Kalibrierung: Stufe 1 = {val} W")

        await self._send_command_raw(CMD_INCREASE)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_2_measure)

    async def _calib_step_2_measure(self, _now):
        val = self._get_current_power()
        self._power_profile[2] = val
        _LOGGER.info(f"Kalibrierung: Stufe 2 = {val} W")

        await self._send_command_raw(CMD_INCREASE)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_3_measure)

    async def _calib_step_3_measure(self, _now):
        val = self._get_current_power()
        self._power_profile[3] = val
        _LOGGER.info(f"Kalibrierung: Stufe 3 = {val} W")

        await self._send_command_raw(CMD_BOOST)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_boost_measure)

    async def _calib_step_boost_measure(self, _now):
        val = self._get_current_power()
        self._power_profile["boost"] = val
        _LOGGER.info(f"Kalibrierung: Boost = {val} W")

        await self._send_command_raw(CMD_TURN_ON_OFF)
        
        self._is_calibrating = False
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self.async_write_ha_state()
        _LOGGER.info("Kalibrierung abgeschlossen. Werte gespeichert.")

    def _get_current_power(self):
        if not self._power_sensor: return 0.0
        state = self.hass.states.get(self._power_sensor)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                return float(state.state)
            except ValueError:
                pass
        return 0.0

    async def _send_command_raw(self, command):
        """Sendet einen Befehl an die Remote mit Hold-Zeit."""
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

    # --- NORMALE STEUERUNG ---

    async def _send_command(self, command):
        await self._send_command_raw(command)
        await asyncio.sleep(DEFAULT_DELAY)

    def _cancel_run_on_timer(self):
        if self._run_on_cancel_fn:
            self._run_on_cancel_fn()
            self._run_on_cancel_fn = None
        self._run_on_active = False

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        if self._is_calibrating: return

        was_in_run_on = self._run_on_active
        self._cancel_run_on_timer()

        if not self._is_on:
            if was_in_run_on:
                _LOGGER.debug("Übernehme aktiven Nachlauf in normalen Betrieb.")
            else:
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
        if self._is_calibrating: return

        if (self._is_on and 
            self._runtime_data.run_on_enabled and 
            not self._run_on_active):
            
            _LOGGER.info("Nachlauf aktiviert. Schalte auf Stufe 1 für %s Sekunden.", self._runtime_data.run_on_seconds)
            
            await self.async_set_percentage(33)
            
            delay = self._runtime_data.run_on_seconds 
            
            self._runtime_data.run_on_finish_time = dt_util.utcnow() + timedelta(seconds=delay)
            self._run_on_active = True 
            
            self._is_on = False
            self._percentage = 0
            self._preset_mode = None
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
        was_in_run_on = self._run_on_active
        self._cancel_run_on_timer()

        if self._is_on or was_in_run_on:
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = False
            self._percentage = 0
            self._current_speed_step = 0
            self._preset_mode = None
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if self._is_calibrating: return

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
        if current == 0:
            current = 1

        diff = target_step - current
        
        _LOGGER.debug(f"Set Percentage: {percentage}% -> Target Step: {target_step} (Current: {current}, Diff: {diff})")

        if diff > 0:
            for _ in range(diff):
                _LOGGER.debug("Sende CMD_INCREASE")
                await self._send_command(CMD_INCREASE)
        elif diff < 0:
            for _ in range(abs(diff)):
                _LOGGER.debug("Sende CMD_DECREASE")
                await self._send_command(CMD_DECREASE)

        self._current_speed_step = target_step
        self._percentage = SPEED_MAPPING[target_step]
        self._preset_mode = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if self._is_calibrating: return
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