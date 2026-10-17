"""Konstanten für die Faber Skypad Integration."""

DOMAIN = "faber_skypad"

# Konfigurations-Schlüssel
CONF_REMOTE_ENTITY = "remote_entity"
CONF_POWER_SENSOR = "power_sensor"
CONF_SYNC_DELAY = "sync_delay"   # Sperrzeit (s) der Zustandserkennung nach eigenen Befehlen

# Standardwerte
DEFAULT_RUN_ON_SECONDS = 60
DEFAULT_DELAY = 0.75
CMD_HOLD_SECS = 0.4
CMD_MAX_RETRIES = 3            # Wiederholungen, wenn sich die Leistung nach einem Befehl nicht ändert

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
MATCH_TOLERANCE = 15.0         # Obergrenze der Matching-Toleranz (W)
MIN_MATCH_TOLERANCE = 2.0      # Untergrenze der Matching-Toleranz (W)
FALLBACK_THRESHOLD = 15.0

# Kalibrierung: jeder Befehl wird über den Leistungssensor bestätigt
CALIB_MIN_CHANGE = 3.0         # Mindeständerung (W), die einen Befehl bestätigt
CALIB_CHANGE_TIMEOUT = 15.0   # Wartezeit (s) auf die Leistungsänderung pro Versuch
CALIB_MAX_ATTEMPTS = 3         # Versuche pro Befehl, danach Abbruch
CALIB_STABLE_WINDOW = 8.0      # Zeitfenster (s), in dem die Leistung stabil sein muss
CALIB_STABLE_BAND = 2.0        # Maximale Schwankung (W) innerhalb des Fensters
CALIB_STABLE_TIMEOUT = 45.0    # Maximale Wartezeit (s) auf einen stabilen Wert
CALIB_COMMAND_GAP = 2.0        # Mindestabstand (s) zwischen zwei Befehlen
CALIB_POLL_INTERVAL = 0.5      # Abtastintervall (s) des Leistungssensors

# Zustandserkennung im Normalbetrieb
DETECTION_SETTLE_TIME = 4.0    # Erkannter Zustand muss so lange (s) anliegen
COMMAND_SETTLE_TIME = 8.0      # Standard für CONF_SYNC_DELAY: nach eigenen Befehlen (s) keine Übernahme
SYNC_DELAY_MAX = 300           # Obergrenze (s) für CONF_SYNC_DELAY
RETRY_CHECK_DELAY = 10.0       # Mindestwartezeit (s) bis zur Prüfung, ob ein Befehl gewirkt hat