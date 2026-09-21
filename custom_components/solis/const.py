DOMAIN = "solis"
DEFAULT_TCP_PORT = 8899

# The logger reports roughly every 5 minutes while the inverter is awake and
# stops completely at night. After this many seconds of silence the data is
# considered stale (three missed reports).
STALE_TIMEOUT = 15 * 60
