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
    CMD_LIGHT,
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

    fan = FaberFan(hass, name, remote_entity, power_sensor, config_entry, runtime_data)
    # Fan in Runtime Data registrieren für Button Zugriff
    runtime_data.fan_entity = fan
    
    async_add_entities([fan])


class FaberFan(FanEntity):
    """Repräsentation des Faber Skypad Lüfters."""

    def __init__(self, hass, name, remote_entity, power_sensor, config_entry, runtime_data):
        self.hass = hass
        self._name = name
        self._remote_entity = remote_entity
        self._power_sensor = power_sensor
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        self._runtime_data = runtime_data
        
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0
        
        self._run_on_cancel_fn = None
        
        # Kalibrierungs-Daten
        self._is_calibrating = False
        self._calibration_step = 0
        self._calibration_step_cancel = None
        self._power_profile = self._config_entry.data.get("power_profile", {
            "off": 0.0,
            "light_on": 0.0,
            "fan_1": 0.0,
            "fan_1_light": 0.0,
            "fan_2": 0.0,
            "fan_2_light": 0.0,
            "fan_3": 0.0,
            "fan_3_light": 0.0,
            "fan_boost": 0.0,
            "fan_boost_light": 0.0,
        })

        # Retry-Logik Daten
        self._retry_check_cancel_fn = None
        self._power_before_command = 0.0
        self._pending_command = None
        self._pending_command_retries = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer="Faber",
            model="Skypad",
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
            attrs["power_profile_light_on"] = f"{self._power_profile.get('light_on', 0):.1f} W"
            attrs["power_profile_1"] = f"{self._power_profile.get('fan_1', 0):.1f} W"
            attrs["power_profile_1_light"] = f"{self._power_profile.get('fan_1_light', 0):.1f} W"
            attrs["power_profile_2"] = f"{self._power_profile.get('fan_2', 0):.1f} W"
            attrs["power_profile_2_light"] = f"{self._power_profile.get('fan_2_light', 0):.1f} W"
            attrs["power_profile_3"] = f"{self._power_profile.get('fan_3', 0):.1f} W"
            attrs["power_profile_3_light"] = f"{self._power_profile.get('fan_3_light', 0):.1f} W"
            attrs["power_profile_boost"] = f"{self._power_profile.get('fan_boost', 0):.1f} W"
            attrs["power_profile_boost_light"] = f"{self._power_profile.get('fan_boost_light', 0):.1f} W"
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
                    # Nur zuweisen, wenn noch kein "off" gelernt wurde
                    if self._power_profile.get("off", 0.0) == 0.0:
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

        # Wenn ein Befehl aussteht, prüfe ob die Leistungsänderung den Erfolg bestätigt
        if self._pending_command:
            power_diff = abs(current_power - self._power_before_command)
            if power_diff >= 3.0:
                _LOGGER.debug("Leistungssensor-Änderung bestätigt Befehlserfolg (Diff: %.1fW). Breche Wiederholungstimer ab.", power_diff)
                self._cancel_retry_check()

        # Profil-Matching
        best_match = None
        min_diff = 0.0

        is_calibrated = (self._power_profile.get("fan_1", 0.0) != 0.0)

        if not is_calibrated:
            # Fallback Logik wenn keine Kalibrierung vorhanden
            p_off = self._power_profile.get("off", 0.0)
            if current_power > p_off + FALLBACK_THRESHOLD:
                best_match = "fan_1"
                detected_fan_on = True
                detected_fan_speed = 1
                detected_fan_preset = None
                detected_light_on = False
            elif current_power >= p_off + 6.0:
                best_match = "light_on"
                detected_fan_on = False
                detected_fan_speed = 0
                detected_fan_preset = None
                detected_light_on = True
            else:
                best_match = "off"
                detected_fan_on = False
                detected_fan_speed = 0
                detected_fan_preset = None
                detected_light_on = False
        else:
            # Kalibrierte Logik mit Hysterese für Licht
            speed_steps = {
                "off": ("off", "light_on"),
                "fan_1": ("fan_1", "fan_1_light"),
                "fan_2": ("fan_2", "fan_2_light"),
                "fan_3": ("fan_3", "fan_3_light"),
                "fan_boost": ("fan_boost", "fan_boost_light"),
            }

            # Bestimme die Lüfterstufe basierend auf dem Mittelwert der jeweiligen Stufe
            best_speed = None
            min_speed_diff = float("inf")
            for speed, (base_key, light_key) in speed_steps.items():
                w_base = self._power_profile.get(base_key, 0.0)
                w_light = self._power_profile.get(light_key, 0.0)
                if w_light == 0.0 and speed != "off":
                    w_light = w_base + 8.0
                
                midpoint = (w_base + w_light) / 2.0
                diff = abs(current_power - midpoint)
                if diff < min_speed_diff:
                    min_speed_diff = diff
                    best_speed = speed

            # Bestimme den Lichtstatus mit Hysterese
            base_key, light_key = speed_steps[best_speed]
            w_base = self._power_profile.get(base_key, 0.0)
            w_light = self._power_profile.get(light_key, 0.0)
            if w_light == 0.0:
                w_light = w_base + 8.0

            delta_p_light = max(w_light - w_base, 6.0)

            light_entity = self._runtime_data.light_entity
            light_was_on = light_entity.is_on if light_entity else False

            if light_was_on:
                # Licht bleibt an, außer die Leistung fällt unter base + 30% des Lichtverbrauchs
                detected_light_on = (current_power >= w_base + 0.3 * delta_p_light)
            else:
                # Licht bleibt aus, außer die Leistung steigt über base + 70% des Lichtverbrauchs
                detected_light_on = (current_power >= w_base + 0.7 * delta_p_light)

            detected_fan_on = (best_speed != "off")
            detected_fan_speed = 0
            detected_fan_preset = None

            if best_speed == "fan_1":
                detected_fan_speed = 1
            elif best_speed == "fan_2":
                detected_fan_speed = 2
            elif best_speed == "fan_3":
                detected_fan_speed = 3
            elif best_speed == "fan_boost":
                detected_fan_speed = 3
                detected_fan_preset = PRESET_BOOST

            best_match = f"{best_speed}{'_light' if detected_light_on else ''}"
            if best_match == "off_light":
                best_match = "light_on"

            # Berechne min_diff zum erwarteten Wert des gematchten Status
            matched_watt = self._power_profile.get(best_match, 0.0)
            if matched_watt == 0.0:
                matched_watt = w_light if detected_light_on else w_base
            min_diff = abs(current_power - matched_watt)

        # Spezialfall Nachlauf: Wenn Nachlauf aktiv, nicht auf "An" synchen
        if self._run_on_active:
             if not detected_fan_on:
                 self._cancel_run_on_timer()
                 self._is_on = False
                 self.async_write_ha_state()
             return

        # Synchronisierung
        if min_diff <= MATCH_TOLERANCE or (best_match == "off") or (self._power_profile.get("fan_1", 0.0) == 0.0):
            # Check if fan state needs update
            fan_changed = (
                detected_fan_on != self._is_on or
                (detected_fan_on and (
                    detected_fan_speed != self._current_speed_step or
                    detected_fan_preset != self._preset_mode
                ))
            )
            if fan_changed:
                _LOGGER.debug(f"Sync Fan: Erkannt={best_match} ({current_power}W), Diff={min_diff:.1f}")
                
                self._is_on = detected_fan_on
                if not detected_fan_on:
                    self._percentage = 0
                    self._current_speed_step = 0
                    self._preset_mode = None
                else:
                    self._preset_mode = detected_fan_preset
                    if detected_fan_preset == PRESET_BOOST:
                         self._percentage = 100
                         self._current_speed_step = 3
                    else:
                        self._current_speed_step = detected_fan_speed
                        self._percentage = SPEED_MAPPING[detected_fan_speed]

                self.async_write_ha_state()

            # Sync Light
            light_entity = self._runtime_data.light_entity
            if light_entity is not None:
                if detected_light_on != light_entity.is_on:
                    _LOGGER.debug(f"Sync Light: Erkannt={best_match} ({current_power}W), Diff={min_diff:.1f}")
                    light_entity.set_state_externally(detected_light_on)

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

    # --- COMMAND RETRY LOGIK ---

    def _cancel_retry_check(self):
        """Bricht einen geplanten Wiederholungstimer ab."""
        if self._retry_check_cancel_fn:
            self._retry_check_cancel_fn()
            self._retry_check_cancel_fn = None

    async def send_command_with_retry(self, command, retry_count=0):
        """Sendet einen Befehl und prüft nach 2 bzw. 5 Sekunden, ob sich die Leistung geändert hat."""
        if not self._power_sensor or self._is_calibrating:
            # Ohne Leistungssensor oder während der Kalibrierung direkt senden
            await self._send_command_raw(command)
            return

        # Bei der ersten Ausführung (retry_count == 0) Leistung aufzeichnen
        if retry_count == 0:
            self._cancel_retry_check()
            self._power_before_command = self._get_current_power()
            self._pending_command = command

        self._pending_command_retries = retry_count

        _LOGGER.debug(
            "Sende Befehl (Versuch %d): %s. Leistung vor dem ersten Versuch: %.1fW",
            retry_count + 1,
            command,
            self._power_before_command
        )
        await self._send_command_raw(command)

        # Erster Retry nach 10 Sekunden, danach alle 10 Sekunden (endlos bis Erfolg)
        delay = 10.0

        self._retry_check_cancel_fn = async_call_later(
            self.hass, delay, self._async_check_power_change
        )

    async def _async_check_power_change(self, _now):
        """Überprüft, ob sich die Leistung seit dem ersten Senden geändert hat. Wenn nicht, wird wiederholt."""
        if self._is_calibrating or not self._pending_command:
            return

        current_power = self._get_current_power()
        power_diff = abs(current_power - self._power_before_command)
        
        # 3.0W Toleranz
        if power_diff < 3.0:
            _LOGGER.warning(
                "Leistung hat sich nach Befehl nicht geändert (Vorher: %.1fW, Jetzt: %.1fW). Wiederhole Befehl %s (Versuch %d)...",
                self._power_before_command,
                current_power,
                self._pending_command,
                self._pending_command_retries + 2
            )
            await self.send_command_with_retry(
                self._pending_command,
                retry_count=self._pending_command_retries + 1
            )
        else:
            _LOGGER.debug(
                "Befehl %s erfolgreich (Leistung geändert von %.1fW auf %.1fW nach %d Versuchen).",
                self._pending_command,
                self._power_before_command,
                current_power,
                self._pending_command_retries + 1
            )
            self._pending_command = None

    # --- KALIBRIERUNG LOGIK ---

    async def async_start_calibration(self):
        """Startet den automatischen Lernlauf."""
        if self._is_calibrating:
            _LOGGER.warning("Kalibrierung läuft bereits.")
            return

        _LOGGER.info("Starte Faber Skypad Kalibrierung... Bitte stellen Sie sicher, dass Lüfter und Licht ausgeschaltet sind.")
        self._is_calibrating = True
        self._calibration_step = 0
        self._runtime_data.trigger_update()
        self.async_write_ha_state()

        # Step 0: Baseline (Alles aus) messen
        # Da wir annehmen, dass alles aus ist, warten wir nur auf das Einpendeln
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_0_measure_off)

    async def async_cancel_calibration(self):
        """Bricht den Kalibrierungsprozess vorzeitig ab und schaltet alles aus."""
        if not self._is_calibrating:
            return
        _LOGGER.info("Kalibrierung manuell abgebrochen.")
        
        # Abbrechen aller ausstehenden Timer
        if self._calibration_step_cancel:
            self._calibration_step_cancel()
            self._calibration_step_cancel = None
            
        # Ermittle den aktuellen Zustand anhand des Schritts und schalte gezielt aus
        # Licht ausschalten, falls es an war (Schritte: 1, 3, 5, 7, 9)
        if self._calibration_step in (1, 3, 5, 7, 9):
            await self._send_command_raw(CMD_LIGHT)
            
        # Lüfter ausschalten, falls er an war (Schritte: 2, 3, 4, 5, 6, 7, 8, 9)
        if self._calibration_step in (2, 3, 4, 5, 6, 7, 8, 9):
            await self._send_command_raw(CMD_TURN_ON_OFF)
            
        self._is_calibrating = False
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0
        self._calibration_step = 0
        
        self._runtime_data.trigger_update()
        self.async_write_ha_state()
        
        light_entity = self._runtime_data.light_entity
        if light_entity is not None:
            light_entity.set_state_externally(False)

    async def _calib_step_0_measure_off(self, _now):
        val = self._get_current_power()
        self._power_profile["off"] = val
        _LOGGER.info(f"Kalibrierung: Baseline (Off) = {val} W")
        
        # Licht einschalten
        self._calibration_step = 1
        await self._send_command(CMD_LIGHT)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_1_measure_light_on)

    async def _calib_step_1_measure_light_on(self, _now):
        val = self._get_current_power()
        self._power_profile["light_on"] = val
        _LOGGER.info(f"Kalibrierung: Licht An = {val} W")
        
        # Licht aus, Lüfter an (Stufe 1)
        self._calibration_step = 2
        await self._send_command(CMD_LIGHT)
        await self._send_command(CMD_TURN_ON_OFF)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_2_measure_fan_1)

    async def _calib_step_2_measure_fan_1(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_1"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 1 = {val} W")
        
        # Licht an
        self._calibration_step = 3
        await self._send_command(CMD_LIGHT)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_3_measure_fan_1_light)

    async def _calib_step_3_measure_fan_1_light(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_1_light"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 1 + Licht = {val} W")
        
        # Licht aus, Lüfter auf Stufe 2 erhöhen
        self._calibration_step = 4
        await self._send_command(CMD_LIGHT)
        await self._send_command(CMD_INCREASE)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_4_measure_fan_2)

    async def _calib_step_4_measure_fan_2(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_2"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 2 = {val} W")
        
        # Licht an
        self._calibration_step = 5
        await self._send_command(CMD_LIGHT)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_5_measure_fan_2_light)

    async def _calib_step_5_measure_fan_2_light(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_2_light"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 2 + Licht = {val} W")
        
        # Licht aus, Lüfter auf Stufe 3 erhöhen
        self._calibration_step = 6
        await self._send_command(CMD_LIGHT)
        await self._send_command(CMD_INCREASE)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_6_measure_fan_3)

    async def _calib_step_6_measure_fan_3(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_3"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 3 = {val} W")
        
        # Licht an
        self._calibration_step = 7
        await self._send_command(CMD_LIGHT)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_7_measure_fan_3_light)

    async def _calib_step_7_measure_fan_3_light(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_3_light"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Stufe 3 + Licht = {val} W")
        
        # Licht aus, Boost aktivieren
        self._calibration_step = 8
        await self._send_command(CMD_LIGHT)
        await self._send_command(CMD_BOOST)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_8_measure_fan_boost)

    async def _calib_step_8_measure_fan_boost(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_boost"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Boost = {val} W")
        
        # Licht an
        self._calibration_step = 9
        await self._send_command(CMD_LIGHT)
        self._calibration_step_cancel = async_call_later(self.hass, CALIBRATION_WAIT_TIME, self._calib_step_9_measure_fan_boost_light)

    async def _calib_step_9_measure_fan_boost_light(self, _now):
        val = self._get_current_power()
        self._power_profile["fan_boost_light"] = val
        _LOGGER.info(f"Kalibrierung: Lüfter Boost + Licht = {val} W")
        
        # Licht aus, Lüfter aus
        await self._send_command(CMD_LIGHT)
        await self._send_command(CMD_TURN_ON_OFF)
        
        self._is_calibrating = False
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0
        self._calibration_step = 0
        
        # In ConfigEntry persistieren
        new_data = {
            **self._config_entry.data,
            "power_profile": self._power_profile,
            "last_calibration": dt_util.utcnow().isoformat()
        }
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        
        self._runtime_data.trigger_update()
        self.async_write_ha_state()
        
        # Licht auf aus synchronisieren
        light_entity = self._runtime_data.light_entity
        if light_entity is not None:
            light_entity.set_state_externally(False)

        _LOGGER.info("Kalibrierung erfolgreich abgeschlossen und dauerhaft gespeichert.")

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
        await self.send_command_with_retry(command)
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