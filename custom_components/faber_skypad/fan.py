"""Fan Plattform für Faber Skypad."""
import logging
import asyncio
import statistics
import time
from typing import Any, Optional, Dict, Tuple
from datetime import timedelta

from homeassistant.components import persistent_notification
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
    MATCH_TOLERANCE,
    MIN_MATCH_TOLERANCE,
    FALLBACK_THRESHOLD,
    CMD_MAX_RETRIES,
    CALIB_MIN_CHANGE,
    CALIB_CHANGE_TIMEOUT,
    CALIB_MAX_ATTEMPTS,
    CALIB_STABLE_WINDOW,
    CALIB_STABLE_BAND,
    CALIB_STABLE_TIMEOUT,
    CALIB_COMMAND_GAP,
    CALIB_POLL_INTERVAL,
    DETECTION_SETTLE_TIME,
    COMMAND_SETTLE_TIME,
)

_LOGGER = logging.getLogger(__name__)

# Reihenfolge der Profile, jede Stufe muss deutlich über der vorherigen liegen
PROFILE_ORDER = [
    ("off", "light_on"),
    ("off", "fan_1"),
    ("fan_1", "fan_2"),
    ("fan_2", "fan_3"),
    ("fan_3", "fan_boost"),
]
FAN_LEVELS = ["off", "fan_1", "fan_2", "fan_3", "fan_boost"]


class CalibrationError(Exception):
    """Kalibrierung fehlgeschlagen (Befehl nicht bestätigt, Werte unplausibel)."""


class CalibrationAborted(Exception):
    """Kalibrierung wurde vom Benutzer abgebrochen."""


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
        self._calibration_task = None
        self._calib_abort_requested = False
        self._calib_restoring = False
        self._calib_last_command = 0.0
        # Bekannter Gerätezustand während der Kalibrierung (None = unbekannt)
        self._calib_fan_on = None
        self._calib_light_on = None
        self._power_profile = self._config_entry.data.get("power_profile", {
            "off": 0.0,
            "light_on": 0.0,
            "fan_1": 0.0,
            "fan_2": 0.0,
            "fan_3": 0.0,
            "fan_boost": 0.0,
        })

        # Retry-Logik Daten
        self._retry_check_cancel_fn = None
        self._power_before_command = 0.0
        self._pending_command = None
        self._pending_command_retries = 0

        # Entprellung der Zustandserkennung
        self._pending_detection = None
        self._detection_cancel_fn = None
        self._sync_suppressed_until = 0.0

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
            attrs["power_profile_2"] = f"{self._power_profile.get('fan_2', 0):.1f} W"
            attrs["power_profile_3"] = f"{self._power_profile.get('fan_3', 0):.1f} W"
            attrs["power_profile_boost"] = f"{self._power_profile.get('fan_boost', 0):.1f} W"
        return attrs

    async def async_added_to_hass(self):
        if self._power_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._power_sensor], self._async_power_sensor_changed
                )
            )

    async def async_will_remove_from_hass(self):
        """Stoppt laufende Kalibrierung und Timer beim Entladen."""
        if self._calibration_task and not self._calibration_task.done():
            self._calibration_task.cancel()
        self._cancel_retry_check()
        self._cancel_pending_detection()

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
                self._pending_command = None

        detection = self._match_power(current_power)
        if detection is None:
            # Keine sichere Zuordnung (z.B. Lüfter läuft gerade hoch/runter)
            self._cancel_pending_detection()
            return

        if detection == self._pending_detection:
            # Gleicher Zustand wie zuvor erkannt, Timer läuft bereits
            return

        # Neuer Zustand muss erst DETECTION_SETTLE_TIME lang anliegen
        self._cancel_pending_detection()
        self._pending_detection = detection
        self._detection_cancel_fn = async_call_later(
            self.hass, DETECTION_SETTLE_TIME, self._async_detection_settled
        )

    def _cancel_pending_detection(self):
        if self._detection_cancel_fn:
            self._detection_cancel_fn()
            self._detection_cancel_fn = None
        self._pending_detection = None

    @callback
    def _async_detection_settled(self, _now):
        """Übernimmt einen stabil erkannten Zustand."""
        self._detection_cancel_fn = None
        if self._is_calibrating or self._pending_detection is None:
            self._pending_detection = None
            return

        # Kurz nach eigenen Befehlen läuft der Lüfter noch hoch/runter -> später prüfen.
        # Solange ein Befehl unbestätigt ist, kümmert sich die Retry-Logik darum.
        remaining = self._sync_suppressed_until - time.monotonic()
        if self._pending_command:
            remaining = max(remaining, DETECTION_SETTLE_TIME)
        if remaining > 0:
            self._detection_cancel_fn = async_call_later(
                self.hass, remaining + 0.1, self._async_detection_settled
            )
            return

        level, light_on = self._pending_detection
        self._pending_detection = None
        self._apply_detection(level, light_on)

    def _get_light_power(self) -> float:
        """Leistung des Lichts laut Kalibrierung (Fallback 8 W)."""
        p_off = self._power_profile.get("off", 0.0)
        p_light_on = self._power_profile.get("light_on", 0.0)
        light_power = max(p_light_on - p_off, 0.0)
        return light_power if light_power > 0.0 else 8.0

    def _get_match_tolerance(self) -> float:
        """Halber kleinster Abstand zwischen zwei unterscheidbaren Zuständen."""
        values = sorted(self._power_profile.get(level, 0.0) for level in FAN_LEVELS)
        gaps = [b - a for a, b in zip(values, values[1:])]
        gaps.append(self._get_light_power())
        min_gap = min(gap for gap in gaps if gap > 0.0) if any(gap > 0.0 for gap in gaps) else 2 * MATCH_TOLERANCE
        return min(max(min_gap / 2.0, MIN_MATCH_TOLERANCE), MATCH_TOLERANCE)

    def _match_power(self, current_power) -> Optional[Tuple[str, Optional[bool]]]:
        """Ordnet eine Leistung einem Zustand (Lüfterstufe, Licht an/aus/unbekannt) zu."""
        p_off = self._power_profile.get("off", 0.0)
        is_calibrated = (self._power_profile.get("fan_1", 0.0) != 0.0)

        if not is_calibrated:
            # Fallback ohne Kalibrierung: nur an/aus, Licht unbekannt
            if current_power > p_off + FALLBACK_THRESHOLD:
                return ("on", None)
            return ("off", None)

        light_power = self._get_light_power()
        tolerance = self._get_match_tolerance()

        light_entity = self._runtime_data.light_entity
        light_is_on = light_entity.is_on if light_entity else False

        def best_level(light_on):
            offset = light_power if light_on else 0.0
            return min(
                (abs(current_power - (self._power_profile.get(level, 0.0) + offset)), level)
                for level in FAN_LEVELS
            )

        # Bevorzugt die Annahme, die zum aktuellen Lichtzustand in HA passt
        diff, level = best_level(light_is_on)
        if diff <= tolerance:
            return (level, light_is_on if light_entity else None)

        # Nur wenn der HA-Lichtzustand nicht passt, der andere aber eindeutig schon
        if light_entity:
            diff_other, level_other = best_level(not light_is_on)
            if diff_other <= tolerance:
                return (level_other, not light_is_on)

        _LOGGER.debug(
            "Keine Zuordnung für %.1fW (bestes Profil %s, Diff %.1fW > Toleranz %.1fW)",
            current_power, level, diff, tolerance
        )
        return None

    def _apply_detection(self, level, light_on):
        """Übernimmt einen erkannten Zustand in Fan und Licht."""
        light_entity = self._runtime_data.light_entity
        if light_on is not None and light_entity is not None and light_entity.is_on != light_on:
            _LOGGER.debug("Sync Licht: Erkannt=%s", "an" if light_on else "aus")
            light_entity.set_state_externally(light_on)

        detected_fan_on = (level != "off")

        # Spezialfall Nachlauf: Wenn Nachlauf aktiv, nicht auf "An" synchen
        if self._run_on_active:
            if not detected_fan_on:
                self._cancel_run_on_timer()
                self._is_on = False
                self.async_write_ha_state()
            return

        if level == "on":
            # Ohne Kalibrierung ist nur "läuft" bekannt, Stufe beibehalten
            if not self._is_on:
                _LOGGER.debug("Sync Fan: Erkannt=an (unkalibriert)")
                self._is_on = True
                self._current_speed_step = 1
                self._percentage = SPEED_MAPPING[1]
                self._preset_mode = None
                self.async_write_ha_state()
            return

        detected_fan_speed = 0
        detected_fan_preset = None
        if level == "fan_1":
            detected_fan_speed = 1
        elif level == "fan_2":
            detected_fan_speed = 2
        elif level == "fan_3":
            detected_fan_speed = 3
        elif level == "fan_boost":
            detected_fan_speed = 3
            detected_fan_preset = PRESET_BOOST

        fan_changed = (
            detected_fan_on != self._is_on or
            (detected_fan_on and (
                detected_fan_speed != self._current_speed_step or
                detected_fan_preset != self._preset_mode
            ))
        )
        if not fan_changed:
            return

        _LOGGER.debug("Sync Fan: Erkannt=%s", level)
        self._is_on = detected_fan_on
        if not detected_fan_on:
            self._percentage = 0
            self._current_speed_step = 0
            self._preset_mode = None
        else:
            self._preset_mode = detected_fan_preset
            self._current_speed_step = detected_fan_speed
            self._percentage = SPEED_MAPPING[detected_fan_speed]

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

    # --- COMMAND RETRY LOGIK ---

    def _cancel_retry_check(self):
        """Bricht einen geplanten Wiederholungstimer ab."""
        if self._retry_check_cancel_fn:
            self._retry_check_cancel_fn()
            self._retry_check_cancel_fn = None

    async def send_command_with_retry(self, command, retry_count=0):
        """Sendet einen Befehl und prüft nach 10 Sekunden, ob sich die Leistung geändert hat."""
        if self._is_calibrating:
            # Während der Kalibrierung steuert nur die Kalibrierung selbst das Gerät
            _LOGGER.debug("Kalibrierung läuft, Befehl %s wird ignoriert.", command)
            return

        # Zustandserkennung erst übernehmen, wenn sich das Gerät eingependelt hat
        self._sync_suppressed_until = time.monotonic() + COMMAND_SETTLE_TIME

        if not self._power_sensor:
            await self._send_command_raw(command)
            return

        # Bei der ersten Ausführung (retry_count == 0) Leistung aufzeichnen
        if retry_count == 0:
            self._cancel_retry_check()
            self._pending_command = None
            power = self._read_power()
            if power is None:
                # Ohne gültigen Messwert würde jeder Retry das Gerät erneut umschalten
                _LOGGER.warning(
                    "Leistungssensor %s liefert keinen Wert, sende Befehl ohne Wiederholung.",
                    self._power_sensor
                )
                await self._send_command_raw(command)
                return
            self._power_before_command = power
            self._pending_command = command

        self._pending_command_retries = retry_count

        _LOGGER.debug(
            "Sende Befehl (Versuch %d): %s. Leistung vor dem ersten Versuch: %.1fW",
            retry_count + 1,
            command,
            self._power_before_command
        )
        await self._send_command_raw(command)

        # Prüfung nach 10 Sekunden, höchstens CMD_MAX_RETRIES Wiederholungen
        delay = 10.0

        self._retry_check_cancel_fn = async_call_later(
            self.hass, delay, self._async_check_power_change
        )

    async def _async_check_power_change(self, _now):
        """Überprüft, ob sich die Leistung seit dem ersten Senden geändert hat. Wenn nicht, wird wiederholt."""
        if self._is_calibrating or not self._pending_command:
            return

        current_power = self._read_power()
        if current_power is None:
            _LOGGER.warning("Leistungssensor liefert keinen Wert, keine Wiederholung von %s.", self._pending_command)
            self._pending_command = None
            return
        power_diff = abs(current_power - self._power_before_command)

        # 3.0W Toleranz
        if power_diff < 3.0 and self._pending_command_retries >= CMD_MAX_RETRIES:
            _LOGGER.warning(
                "Befehl %s nach %d Versuchen ohne Leistungsänderung (%.1fW), gebe auf.",
                self._pending_command,
                self._pending_command_retries + 1,
                current_power
            )
            self._pending_command = None
        elif power_diff < 3.0:
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
        if not self._power_sensor:
            _LOGGER.warning("Kalibrierung benötigt einen Leistungssensor.")
            return
        if self._read_power() is None:
            _LOGGER.error("Kalibrierung nicht gestartet: Leistungssensor %s liefert keinen Wert.", self._power_sensor)
            persistent_notification.async_create(
                self.hass,
                f"Die Kalibrierung wurde nicht gestartet: Der Leistungssensor `{self._power_sensor}` "
                "existiert nicht oder liefert keinen Wert. Bitte unter „Konfigurieren“ den richtigen Sensor wählen.",
                title=f"{self._name}: Kalibrierung",
                notification_id=f"{DOMAIN}_{self._entry_id}_calibration",
            )
            self._runtime_data.trigger_update()
            return

        _LOGGER.info("Starte Faber Skypad Kalibrierung.")
        self._is_calibrating = True
        self._calib_abort_requested = False
        self._calib_fan_on = None
        self._calib_light_on = None

        # Offene Befehle, Nachlauf und Erkennung dürfen die Kalibrierung nicht stören
        self._cancel_retry_check()
        self._pending_command = None
        self._cancel_pending_detection()
        self._cancel_run_on_timer()

        self._runtime_data.trigger_update()
        self.async_write_ha_state()

        self._calibration_task = self.hass.async_create_task(self._async_run_calibration())

    async def async_cancel_calibration(self):
        """Bricht die Kalibrierung ab. Das Gerät wird anschließend kontrolliert ausgeschaltet."""
        if not self._is_calibrating:
            return
        _LOGGER.info("Kalibrierung manuell abgebrochen, schalte Geräte aus...")
        self._calib_abort_requested = True

    async def _async_run_calibration(self):
        """Führt die Kalibrierung aus und räumt danach in jedem Fall auf."""
        new_profile = None
        error = None
        try:
            try:
                new_profile = await self._calib_sequence()
            except CalibrationAborted:
                pass
            except CalibrationError as err:
                error = str(err)
                _LOGGER.error("Kalibrierung fehlgeschlagen: %s", error)
            except Exception as err:  # noqa: BLE001 - Aufräumen muss immer laufen
                error = f"Unerwarteter Fehler: {err}"
                _LOGGER.exception("Kalibrierung fehlgeschlagen")

            if new_profile is None:
                try:
                    await self._calib_restore_off()
                except CalibrationError as err:
                    _LOGGER.warning("Geräte konnten nach der Kalibrierung nicht sicher ausgeschaltet werden: %s", err)
                    error = (error + ". " if error else "") + (
                        "Geräte konnten nicht sicher ausgeschaltet werden, bitte Zustand prüfen."
                    )
        except asyncio.CancelledError:
            # Integration wird entladen: nur internen Zustand zurücksetzen
            self._is_calibrating = False
            raise

        self._finish_calibration()

        notification_id = f"{DOMAIN}_{self._entry_id}_calibration"
        if new_profile is not None:
            self._power_profile = new_profile
            new_data = {
                **self._config_entry.data,
                "power_profile": new_profile,
                "last_calibration": dt_util.utcnow().isoformat()
            }
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            self._runtime_data.trigger_update()
            self.async_write_ha_state()
            persistent_notification.async_dismiss(self.hass, notification_id)
            _LOGGER.info("Kalibrierung erfolgreich abgeschlossen und dauerhaft gespeichert: %s", new_profile)
        elif error:
            persistent_notification.async_create(
                self.hass,
                f"Die Kalibrierung ist fehlgeschlagen, das bisherige Profil bleibt erhalten.\n\n{error}",
                title=f"{self._name}: Kalibrierung",
                notification_id=notification_id,
            )

    def _finish_calibration(self):
        """Setzt den HA-Zustand nach der Kalibrierung auf 'alles aus'."""
        self._is_calibrating = False
        self._calib_abort_requested = False
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0

        self._runtime_data.trigger_update()
        self.async_write_ha_state()

        light_entity = self._runtime_data.light_entity
        if light_entity is not None:
            light_entity.set_state_externally(False)

    async def _calib_sequence(self) -> Dict[str, float]:
        """Misst alle Profile. Jeder Befehl wird über die Leistung bestätigt."""
        profile = {}

        # Ausgangszustand herstellen: unabhängig vom Startzustand alles aus
        await self._calib_probe_off(CMD_TURN_ON_OFF, "Lüfter")
        self._calib_fan_on = False
        p_off = await self._calib_probe_off(CMD_LIGHT, "Licht")
        self._calib_light_on = False
        profile["off"] = p_off
        _LOGGER.info("Kalibrierung: Baseline (Off) = %.1f W", p_off)

        profile["light_on"] = await self._calib_toggle_light(True, p_off)
        _LOGGER.info("Kalibrierung: Licht An = %.1f W", profile["light_on"])

        p_off = await self._calib_toggle_light(False, profile["light_on"])

        # Die Haube startet immer auf Stufe 1
        profile["fan_1"] = await self._calib_toggle_fan(True, p_off)
        _LOGGER.info("Kalibrierung: Lüfter Stufe 1 = %.1f W", profile["fan_1"])

        profile["fan_2"] = await self._calib_send_verified(CMD_INCREASE, "Stufe 2", profile["fan_1"], 1)
        _LOGGER.info("Kalibrierung: Lüfter Stufe 2 = %.1f W", profile["fan_2"])

        profile["fan_3"] = await self._calib_send_verified(CMD_INCREASE, "Stufe 3", profile["fan_2"], 1)
        _LOGGER.info("Kalibrierung: Lüfter Stufe 3 = %.1f W", profile["fan_3"])

        profile["fan_boost"] = await self._calib_send_verified(CMD_BOOST, "Boost", profile["fan_3"], 1)
        _LOGGER.info("Kalibrierung: Lüfter Boost = %.1f W", profile["fan_boost"])

        await self._calib_toggle_fan(False, profile["fan_boost"])

        self._validate_power_profile(profile)
        return profile

    async def _calib_restore_off(self):
        """Schaltet Lüfter und Licht nach Abbruch/Fehler kontrolliert aus.

        Ein Abbruch wird hier ignoriert und jedes Gerät einzeln versucht,
        damit die Haube möglichst sicher aus ist.
        """
        self._calib_restoring = True
        errors = []
        try:
            try:
                if self._calib_fan_on is None:
                    await self._calib_probe_off(CMD_TURN_ON_OFF, "Lüfter")
                    self._calib_fan_on = False
                elif self._calib_fan_on:
                    await self._calib_toggle_fan(False, await self._calib_wait_stable())
            except CalibrationError as err:
                errors.append(str(err))

            try:
                if self._calib_light_on is None:
                    await self._calib_probe_off(CMD_LIGHT, "Licht")
                    self._calib_light_on = False
                elif self._calib_light_on:
                    await self._calib_toggle_light(False, await self._calib_wait_stable())
            except CalibrationError as err:
                errors.append(str(err))
        finally:
            self._calib_restoring = False

        if errors:
            raise CalibrationError("; ".join(errors))

    async def _calib_toggle_fan(self, turn_on: bool, baseline: float) -> float:
        # Während des Umschaltens ist der Zustand unbekannt, bis die Leistung ihn bestätigt
        self._calib_fan_on = None
        value = await self._calib_send_verified(
            CMD_TURN_ON_OFF, "Lüfter an" if turn_on else "Lüfter aus", baseline, 1 if turn_on else -1
        )
        self._calib_fan_on = turn_on
        return value

    async def _calib_toggle_light(self, turn_on: bool, baseline: float) -> float:
        self._calib_light_on = None
        value = await self._calib_send_verified(
            CMD_LIGHT, "Licht an" if turn_on else "Licht aus", baseline, 1 if turn_on else -1
        )
        self._calib_light_on = turn_on
        return value

    async def _calib_probe_off(self, command, label) -> float:
        """Schaltet ein Toggle-Gerät sicher aus, egal ob es vorher an oder aus war.

        Einmal umschalten und an der Leistung ablesen, in welche Richtung es ging.
        Stieg die Leistung, war das Gerät aus und wird wieder ausgeschaltet.
        """
        baseline = await self._calib_wait_stable()
        value = await self._calib_send_verified(command, f"{label} umschalten", baseline, 0)
        if value > baseline:
            _LOGGER.info("Kalibrierung: %s war aus (%.1fW -> %.1fW), schalte wieder aus.", label, baseline, value)
            value = await self._calib_send_verified(command, f"{label} aus", value, -1)
        else:
            _LOGGER.info("Kalibrierung: %s war an und ist jetzt aus (%.1fW -> %.1fW).", label, baseline, value)
        return value

    async def _calib_send_verified(self, command, label, baseline: float, direction: int) -> float:
        """Sendet einen Befehl, bis die Leistung sich in die erwartete Richtung ändert.

        direction: 1 = Leistung muss steigen, -1 = fallen, 0 = beliebig.
        Gibt den stabilen Leistungswert nach dem Befehl zurück.
        """
        max_attempts = CALIB_MAX_ATTEMPTS * 2 if self._calib_restoring else CALIB_MAX_ATTEMPTS
        for attempt in range(1, max_attempts + 1):
            # Mindestabstand zwischen zwei IR-Befehlen, sonst gehen sie verloren
            gap = self._calib_last_command + CALIB_COMMAND_GAP - time.monotonic()
            if gap > 0:
                await asyncio.sleep(gap)
            self._calib_check_abort()

            _LOGGER.debug("Kalibrierung: %s (Versuch %d, Ausgangsleistung %.1fW)", label, attempt, baseline)
            await self._send_command_raw(command)
            self._calib_last_command = time.monotonic()

            if await self._calib_wait_for_change(baseline, direction):
                value = await self._calib_wait_stable()
                if self._is_expected_change(value - baseline, direction):
                    return value
                # Nur kurzzeitige Änderung: erneutes Senden könnte doppelt umschalten
                raise CalibrationError(
                    f"{label}: Leistung nur kurzzeitig verändert "
                    f"({baseline:.1f} W -> {value:.1f} W)"
                )

            _LOGGER.warning(
                "Kalibrierung: %s ohne Leistungsänderung (%.1fW), wiederhole Befehl...",
                label, baseline
            )

        raise CalibrationError(
            f"{label}: keine Leistungsänderung nach {max_attempts} Versuchen "
            f"(Leistung {baseline:.1f} W)"
        )

    @staticmethod
    def _is_expected_change(delta: float, direction: int) -> bool:
        if direction > 0:
            return delta >= CALIB_MIN_CHANGE
        if direction < 0:
            return delta <= -CALIB_MIN_CHANGE
        return abs(delta) >= CALIB_MIN_CHANGE

    async def _calib_wait_for_change(self, baseline: float, direction: int) -> bool:
        """Wartet, bis sich die Leistung in die erwartete Richtung ändert."""
        deadline = time.monotonic() + CALIB_CHANGE_TIMEOUT
        while time.monotonic() < deadline:
            self._calib_check_abort()
            power = self._read_power()
            if power is not None and self._is_expected_change(power - baseline, direction):
                return True
            await asyncio.sleep(CALIB_POLL_INTERVAL)
        return False

    async def _calib_wait_stable(self) -> float:
        """Wartet, bis die Leistung CALIB_STABLE_WINDOW Sekunden stabil ist, und liefert den Median."""
        samples = []
        start = time.monotonic()
        while True:
            self._calib_check_abort()
            now = time.monotonic()
            power = self._read_power()
            if power is not None:
                samples.append((now, power))

            window = [p for t, p in samples if t >= now - CALIB_STABLE_WINDOW]
            if window and now - start >= CALIB_STABLE_WINDOW and max(window) - min(window) <= CALIB_STABLE_BAND:
                return statistics.median(window)

            if now - start >= CALIB_STABLE_TIMEOUT:
                if not window:
                    raise CalibrationError("Leistungssensor liefert keine Werte")
                _LOGGER.warning(
                    "Kalibrierung: Leistung nach %ss nicht stabil (%.1f–%.1fW), verwende Median.",
                    CALIB_STABLE_TIMEOUT, min(window), max(window)
                )
                return statistics.median(window)

            await asyncio.sleep(CALIB_POLL_INTERVAL)

    def _calib_check_abort(self):
        if self._calib_abort_requested and not self._calib_restoring:
            raise CalibrationAborted()

    @staticmethod
    def _validate_power_profile(profile: Dict[str, float]) -> None:
        """Prüft, ob die gemessenen Stufen klar unterscheidbar und aufsteigend sind."""
        for lower, higher in PROFILE_ORDER:
            if profile[higher] - profile[lower] < CALIB_MIN_CHANGE:
                raise CalibrationError(
                    f"Unplausible Messwerte: {higher} ({profile[higher]:.1f} W) liegt nicht "
                    f"deutlich über {lower} ({profile[lower]:.1f} W)"
                )

    def _read_power(self) -> Optional[float]:
        if not self._power_sensor:
            return None
        state = self.hass.states.get(self._power_sensor)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                return float(state.state)
            except ValueError:
                pass
        return None

    def _get_current_power(self):
        power = self._read_power()
        return power if power is not None else 0.0

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
            blocking=True,
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