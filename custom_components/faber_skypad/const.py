"""Konstanten für die Faber Skypad Integration."""

DOMAIN = "faber_skypad"

# Konfigurations-Schlüssel
CONF_REMOTE_ENTITY = "remote_entity"
CONF_POWER_SENSOR = "power_sensor"

# Standardwerte
DEFAULT_RUN_ON_SECONDS = 60
DEFAULT_DELAY = 0.75
CMD_HOLD_SECS = 0.4

# Commands - Base64 Codes
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
CALIBRATION_WAIT_TIME = 12.0
MATCH_TOLERANCE = 10.0
FALLBACK_THRESHOLD = 15.0