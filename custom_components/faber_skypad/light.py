"""Licht Plattform für Faber Skypad."""
import logging
# Importieren der notwendigen Home Assistant Komponenten
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo # WICHTIG: Für die Geräte-Verknüpfung

# Importieren eigener Konstanten aus const.py
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
    """
    Richtet die Licht-Plattform basierend auf der Konfiguration ein.
    Wird von Home Assistant beim Start der Integration aufgerufen.
    """
    # Laden der Konfigurationsdaten (gespeichert beim Setup)
    config = hass.data[DOMAIN][config_entry.entry_id]
    remote_entity = config[CONF_REMOTE_ENTITY]
    name = config.get("name", "Faber Skypad")

    # Erstellen der Licht-Entität und Übergabe an Home Assistant
    # Wir übergeben entry_id, um die Entität eindeutig dem Gerät zuzuordnen
    async_add_entities([FaberLight(name, remote_entity, hass, config_entry.entry_id)])


class FaberLight(LightEntity):
    """
    Repräsentation des Faber Skypad Lichts.
    Da es keine Rückmeldung vom Gerät gibt, speichern wir den Status intern.
    """

    def __init__(self, name, remote_entity, hass, entry_id):
        """Initialisierung der Licht-Entität."""
        self._name = f"{name} Licht"  # Der Anzeigename in HA
        self._base_name = name        # Der Name für das übergeordnete Gerät
        self._remote_entity = remote_entity # Die ID des IR-Senders (z.B. remote.broadlink)
        self.hass = hass
        self._entry_id = entry_id     # Notwendig für die Geräte-Gruppierung
        self._is_on = False           # Interner Status-Speicher (Standard: Aus)

    @property
    def device_info(self) -> DeviceInfo:
        """
        Verbindet diese Entität mit demselben Gerät wie den Lüfter.
        Durch gleiche 'identifiers' werden Licht und Lüfter gruppiert.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._base_name,
            manufacturer="Faber",
            model="Skypad",
            via_device=(DOMAIN, self._remote_entity), # Zeigt an, dass es über den IR-Sender läuft
        )

    @property
    def name(self):
        """Gibt den Namen der Entität zurück."""
        return self._name

    @property
    def unique_id(self):
        """
        Eine eindeutige ID für diese spezifische Entität.
        Verhindert Konflikte, wenn mehrere Instanzen installiert sind.
        """
        return f"{self._entry_id}_light"

    @property
    def is_on(self):
        """Gibt zurück, ob das Licht an ist (basierend auf internem Status)."""
        return self._is_on
    
    @property
    def color_mode(self):
        """Gibt den aktuellen Farbmodus zurück (hier nur An/Aus)."""
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        """Gibt an, welche Farbmodi unterstützt werden (nur An/Aus)."""
        return {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs):
        """
        Schaltet das Licht ein.
        Sendet den IR-Befehl nur, wenn wir denken, dass es aus ist.
        """
        if not self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = True
            # Teilt Home Assistant mit, dass sich der Status geändert hat
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """
        Schaltet das Licht aus.
        Sendet den IR-Befehl nur, wenn wir denken, dass es an ist.
        """
        if self._is_on:
            await self._send_command(CMD_LIGHT)
            self._is_on = False
            self.async_write_ha_state()

    async def _send_command(self, command):
        """
        Hilfsfunktion zum Senden der IR Befehle an die Remote-Entität.
        """
        # Sicherstellen, dass der Code das Format 'b64:...' hat
        cmd_formatted = command if command.startswith("b64:") else f"b64:{command}"
        
        # Aufruf des 'remote.send_command' Dienstes
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity,
                "command": [cmd_formatted], # Muss eine Liste sein
            },
        )