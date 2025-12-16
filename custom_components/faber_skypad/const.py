"""Konstanten für die Faber Skypad Integration."""

DOMAIN = "faber_skypad"

CONF_REMOTE_ENTITY = "remote_entity"
CONF_POWER_SENSOR = "power_sensor"

# Standardwerte
DEFAULT_DELAY = 0.5  # Sekunden Pause zwischen IR Signalen

# IR Codes (Base64)
CMD_TURN_ON_OFF = "JgAUABgYFy0vFxgXFi4vQxgsGBcvAA0F"
CMD_INCREASE = "JgASABkXRxcXFxcYRhcYQ0ctMAANBQ=="
CMD_DECREASE = "JgASABgtMBYXFxgtLxcXWi8tLwANBQ=="
CMD_BOOST = "JgASABgYLy0XFxgWLy4XQzBDLwANBQ=="
CMD_LIGHT = "JgAUABkXFxYwLRgWFxcwWRgWFxdIAA0F"