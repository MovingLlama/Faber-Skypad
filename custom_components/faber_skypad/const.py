"""Konstanten für die Faber Skypad Integration."""
from datetime import timedelta

DOMAIN = "faber_skypad"

# Konfigurations-Schlüssel
CONF_REMOTE_ENTITY = "remote_entity"
CONF_POWER_SENSOR = "power_sensor"

# Standardwerte
DEFAULT_RUN_ON_MINUTES = 1   # Korrigiert: 1 Minute Standard
DEFAULT_DELAY = 0.75         # Korrigiert: 0.75 Sekunden Verzögerung

# Commands - BITTE HIER DEINE BASE64 CODES EINFÜGEN
# Das Präfix "b64:" wird automatisch ergänzt, falls es fehlt.
CMD_TURN_ON_OFF = "JgAUABgYFy0vFxgXFi4vQxgsGBcvAA0F"
CMD_INCREASE = "JgASABkXRxcXFxcYRhcYQ0ctMAANBQ=="
CMD_DECREASE = "JgASABgtMBYXFxgtLxcXWi8tLwANBQ=="
CMD_BOOST = "JgASABgYLy0XFxgWLy4XQzBDLwANBQ=="
CMD_LIGHT = "JgAUABkXFxYwLRgWFxcwWRgWFxdIAA0F"


# Logik & Kalibrierung Einstellungen
SPEED_MAPPING = {
    1: 33,
    2: 66,
    3: 100
}

PRESET_BOOST = "BOOST"
# COMMAND_DELAY wurde entfernt, wir nutzen DEFAULT_DELAY
CALIBRATION_WAIT_TIME = 12.0 # Wartezeit vor Messung während Kalibrierung
MATCH_TOLERANCE = 10.0     # Watt Toleranz (+/-) für Stufenerkennung
FALLBACK_THRESHOLD = 15.0  # Watt Puffer zur Erkennung "An", falls keine Kalibrierung existiert