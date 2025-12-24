"""Konstanten für die Faber Skypad Integration."""
from datetime import timedelta

DOMAIN = "faber_skypad"

# Konfigurations-Schlüssel
CONF_REMOTE_ENTITY = "remote_entity"
CONF_POWER_SENSOR = "power_sensor"

# Standardwerte
DEFAULT_RUN_ON_MINUTES = 30
DEFAULT_DELAY = 0.75

# Commands (Base64 oder Namen, je nach Remote Implementierung)
CMD_TURN_ON_OFF = "TURN_ON_OFF"
CMD_INCREASE = "INCREASE"
CMD_DECREASE = "DECREASE"
CMD_BOOST = "BOOST"
CMD_LIGHT = "LIGHT"
CMD_LIGHT_DIM = "LIGHT_DIM"

# Logik & Kalibrierung Einstellungen
SPEED_MAPPING = {
    1: 33,
    2: 66,
    3: 100
}

PRESET_BOOST = "BOOST"
COMMAND_DELAY = 1.0        # Pause zwischen Befehlen in Sekunden
CALIBRATION_WAIT_TIME = 12.0 # Wartezeit vor Messung während Kalibrierung
MATCH_TOLERANCE = 10.0     # Watt Toleranz (+/-) für Stufenerkennung
FALLBACK_THRESHOLD = 15.0  # Watt Puffer zur Erkennung "An", falls keine Kalibrierung existiert