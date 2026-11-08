"""Constants for the ABB B23 integration."""

DOMAIN = "abb_b23"
MANUFACTURER = "ABB"

CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_UNIT_ID = "unit_id"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"

# ABB factory defaults for B21/B23/B24 meters.
DEFAULT_BAUDRATE = 19200
DEFAULT_PARITY = "E"
DEFAULT_STOPBITS = 1
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

SCAN_INTERVAL_SECONDS = 10
# A serial proxy adds a WiFi round trip; give the meter room to answer.
REQUEST_TIMEOUT_SECONDS = 2.0
