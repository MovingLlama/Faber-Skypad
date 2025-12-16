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
from homeassistant.helpers.entity import DeviceInfo  # WICHTIG: Import für Geräte-Zuweisung

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

# Mapping: Welche Stufe entspricht wie viel Prozent in Home Assistant
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
    """
    Richtet die Fan-Plattform basierend auf der Konfiguration ein.
    Wird beim Start der Integration ausgeführt.
    """
    # Laden der gespeicherten Konfiguration
    config = hass.data[DOMAIN][config_entry.entry_id]
    remote_entity = config[CONF_REMOTE_ENTITY]
    power_sensor = config.get(CONF_POWER_SENSOR)
    name = config.get("name", "Faber Skypad")

    # Erstellen der Fan-Entität und Registrierung in Home Assistant
    async_add_entities([FaberFan(hass, name, remote_entity, power_sensor, config_entry.entry_id)])


class FaberFan(FanEntity):
    """
    Repräsentation des Faber Skypad Lüfters.
    Speichert den Status intern, da keine direkte Rückmeldung vom Gerät kommt.
    """

    def __init__(self, hass, name, remote_entity, power_sensor, entry_id):
        """Initialisierung der Klasse."""
        self.hass = hass
        self._name = name
        self._remote_entity = remote_entity # Der IR-Sender
        self._power_sensor = power_sensor   # Optionaler Stromzähler
        self._entry_id = entry_id           # ID für die Geräte-Verknüpfung
        
        # Interne Status-Variablen (Startwerte)
        self._is_on = False
        self._percentage = 0
        self._preset_mode = None
        self._current_speed_step = 0 # Interne Stufe: 0, 1, 2, 3

    @property
    def device_info(self) -> DeviceInfo:
        """
        Definiert das physische Gerät.
        Durch die gleiche ID wie beim Licht werden beide Entitäten gruppiert.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer="Faber",
            model="Skypad",
            via_device=(DOMAIN, self._remote_entity),
        )

    @property
    def name(self):
        """Name der Entität in der UI."""
        return self._name

    @property
    def unique_id(self):
        """Eindeutige ID für diese Entität."""
        return f"{self._entry_id}_fan"

    @property
    def supported_features(self):
        """
        Definiert die Fähigkeiten des Lüfters:
        - Geschwindigkeit setzen
        - An/Aus
        - Preset Modus (für Boost)
        """
        return FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF | FanEntityFeature.PRESET_MODE

    @property
    def is_on(self):
        """Ist der Lüfter an?"""
        return self._is_on

    @property
    def percentage(self):
        """Aktuelle Geschwindigkeit in Prozent."""
        return self._percentage

    @property
    def preset_mode(self):
        """Aktueller Preset Modus (z.B. Boost)."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Liste der verfügbaren Presets."""
        return [PRESET_BOOST]

    async def async_added_to_hass(self):
        """
        Wird aufgerufen, wenn die Entität zu HA hinzugefügt wird.
        Startet das Überwachen des Stromsensors, falls konfiguriert.
        """
        if self._power_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._power_sensor], self._async_power_sensor_changed
                )
            )

    @callback
    def _async_power_sensor_changed(self, event):
        """
        Callback wenn sich der Stromverbrauch ändert.
        Hier kann später die Logik implementiert werden, um den Status
        anhand der Watt-Zahl zu korrigieren (Self-Healing).
        """
        pass

    async def _send_command(self, command):
        """
        Hilfsfunktion: Sendet den IR-Code über den konfigurierten Remote.
        Fügt 'b64:' hinzu, falls nötig.
        """
        cmd_formatted = command if command.startswith("b64:") else f"b64:{command}"
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": [cmd_formatted],
            },
        )
        # Pause, damit der IR-Empfänger am Gerät den nächsten Befehl verarbeiten kann
        await asyncio.sleep(DEFAULT_DELAY)

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """
        Schaltet den Lüfter ein.
        Logik: 'Ein' schaltet immer auf Stufe 1.
        """
        if not self._is_on:
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = True
            self._current_speed_step = 1
            self._percentage = SPEED_MAPPING[1]
        
        # Falls direkt eine bestimmte Stufe oder Boost gewünscht ist
        if percentage:
            await self.async_set_percentage(percentage)
        elif preset_mode:
            await self.async_set_preset_mode(preset_mode)
            
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """
        Schaltet den Lüfter aus.
        """
        if self._is_on:
            await self._send_command(CMD_TURN_ON_OFF)
            self._is_on = False
            self._percentage = 0
            self._current_speed_step = 0
            self._preset_mode = None
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """
        Setzt die Lüftergeschwindigkeit (1-3).
        Berechnet, wie oft 'Plus' oder 'Minus' gedrückt werden muss.
        """
        if percentage == 0:
            await self.async_turn_off()
            return

        if not self._is_on:
            await self.async_turn_on()

        # Ziel-Stufe ermitteln (1, 2 oder 3) basierend auf Prozent
        target_step = 1
        if percentage > 33: target_step = 2
        if percentage > 66: target_step = 3

        # Differenz zur aktuellen Stufe berechnen
        current = self._current_speed_step
        diff = target_step - current

        if diff > 0:
            # Stufe erhöhen: X mal 'Stärker' senden
            for _ in range(diff):
                await self._send_command(CMD_INCREASE)
        elif diff < 0:
            # Stufe verringern: X mal 'Schwächer' senden
            for _ in range(abs(diff)):
                await self._send_command(CMD_DECREASE)

        # Status aktualisieren
        self._current_speed_step = target_step
        self._percentage = SPEED_MAPPING[target_step]
        self._preset_mode = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """
        Aktiviert den Boost-Modus oder kehrt zurück.
        """
        if preset_mode == PRESET_BOOST:
            if not self._is_on:
                await self.async_turn_on()
            
            await self._send_command(CMD_BOOST)
            self._preset_mode = PRESET_BOOST
            
            # Timer starten, um den Boost-Status in der UI nach 5 Minuten zurückzusetzen
            # (da das Gerät dies automatisch tut)
            self.hass.loop.call_later(300, self._reset_boost_status)
        else:
            # Boost verlassen -> zurück zur letzten bekannten Geschwindigkeit
            await self.async_set_percentage(self._percentage)

        self.async_write_ha_state()

    def _reset_boost_status(self):
        """
        Callback-Funktion: Entfernt den Boost-Status in der UI nach Zeitablauf.
        """
        if self._preset_mode == PRESET_BOOST:
            self._preset_mode = None
            self.async_write_ha_state() 