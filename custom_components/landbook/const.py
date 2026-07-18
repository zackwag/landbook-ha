"""Constants for the Landbook integration."""

DOMAIN = "landbook"

# Region config key
CONF_REGION = "region"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BEARER_TOKEN = "bearer_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_UID = "uid"
CONF_DEVICE_KEY = "device_key"
CONF_PRODUCT_KEY = "product_key"
CONF_DEVICE_NAME = "device_name"
CONF_PRODUCT_NAME = "product_name"
CONF_MUTE_ON_COMMAND = "mute_on_command"  # deprecated — migrated to CONF_RESTORE_STATE
CONF_RESTORE_STATE = "restore_state"
CONF_FW_VERSION = "fw_version"
CONF_TEMP_UNIT = "temperature_unit"
TEMP_UNIT_F = "°F"
TEMP_UNIT_C = "°C"
CONF_SIGNAL_STRENGTH = "signal_strength_enabled"
SIGNAL_STRENGTH_POLL_INTERVAL = 300  # seconds

# Access tokens are issued with a 2-hour TTL (JWT exp - iat). Refresh well
# before that so the shared MQTT connection and REST calls never see an
# expired access token under normal operation.
PROACTIVE_TOKEN_REFRESH_INTERVAL = 5400  # seconds (90 minutes)

# TSL property data types
DTYPE_BOOL = "BOOL"
DTYPE_ENUM = "ENUM"
DTYPE_INT = "INT"

# MQTT topic suffixes (device_id = f"qd{pk}{dk}")
MQTT_TOPIC_COMMAND = "sys_"   # publish: commands to device
MQTT_TOPIC_REPORTS = "bus_"   # subscribe: state reports (MATTR)
MQTT_TOPIC_ACK     = "ack_"   # subscribe: command acknowledgements
MQTT_TOPIC_ONLINE  = "onl_"   # subscribe: online/offline events
MQTT_TOPIC_OTA     = "ota_"   # subscribe: OTA updates
MQTT_TOPIC_INFO    = "inf_"   # subscribe: device info push
MQTT_TOPIC_LOCATION= "loc_"   # subscribe: location push
# Will be auto-detected if sort=0 and is BOOL with on/open/enable spec
POWER_SORT_ORDER = 0

# Speed property detection: look for an INT or ENUM property with these name hints
SPEED_NAME_HINTS = ("speed", "wind", "gear", "level")

# Oscillation property detection
OSCILLATION_NAME_HINTS = ("oscillat", "swing", "rotate")

# Display name overrides: TSL property name -> HA entity name
# Keys are case-insensitive matches against p["name"].lower()
DISPLAY_NAME_OVERRIDES = {
    "light": "Device Display",
    "sound": "Device Sound",
}

# Display/backlight BOOL properties that should be light entities
DISPLAY_LIGHT_HINTS = ("light", "display", "backlight", "screen")

# Switch display name overrides and icons
# Keys match TSL property name (lowercase)
SWITCH_ICON_MAP = {
    "sound": "mdi:volume-high",
}

# Temperature property detection
TEMPERATURE_NAME_HINTS = ("temperature", "temp")
