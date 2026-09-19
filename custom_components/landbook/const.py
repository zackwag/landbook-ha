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
# Required for local-LAN control login (see landbook_api.local_client). Only
# present on entries created after that support landed — older entries fall
# back to cloud MQTT if local control is enabled without one on file.
CONF_AUTH_KEY = "auth_key"
# Cached TSL property model (see async_get_tsl) — fetched once and reused
# across restarts instead of an unconditional REST call every setup. TSL
# rarely changes; remove and re-add the device to force a refresh if it
# ever does, same as CONF_AUTH_KEY's existing precedent.
CONF_TSL_CACHE = "tsl_cache"
CONF_FW_VERSION = "fw_version"
CONF_TEMP_UNIT = "temperature_unit"
TEMP_UNIT_F = "°F"
TEMP_UNIT_C = "°C"
CONF_SIGNAL_STRENGTH = "signal_strength_enabled"
SIGNAL_STRENGTH_POLL_INTERVAL = 300  # seconds
CONF_MQTT_WATCHDOG_ENABLED = "mqtt_watchdog_enabled"
# How long to wait for local-LAN discovery replies before giving up and
# falling back to cloud MQTT for accounts that opted in to local control.
# Runs once per account (cached), not per device.
LOCAL_DISCOVERY_TIMEOUT = 5.0  # seconds
LOCAL_CONNECT_TIMEOUT = 10.0  # seconds, matches LandbookLocalClient's default
MQTT_WATCHDOG_CHECK_INTERVAL = 30  # seconds between dead-link checks
MQTT_WATCHDOG_STALE_INTERVAL = 300  # zero-inbound-MQTT time before forcing reconnect

# Access tokens are issued with a 2-hour TTL (JWT exp - iat). Refresh well
# before that so the shared MQTT connection and REST calls never see an
# expired access token under normal operation.
PROACTIVE_TOKEN_REFRESH_INTERVAL = 5400  # seconds (90 minutes)

# TSL property data types
DTYPE_BOOL = "BOOL"
DTYPE_ENUM = "ENUM"
DTYPE_INT = "INT"

# MQTT topic suffixes (device_id = f"qd{pk}{dk}")
MQTT_TOPIC_COMMAND = "sys_"  # publish: commands to device
MQTT_TOPIC_REPORTS = "bus_"  # subscribe: state reports (MATTR)
MQTT_TOPIC_ACK = "ack_"  # subscribe: command acknowledgements
MQTT_TOPIC_ONLINE = "onl_"  # subscribe: online/offline events
MQTT_TOPIC_OTA = "ota_"  # subscribe: OTA updates
MQTT_TOPIC_INFO = "inf_"  # subscribe: device info push
MQTT_TOPIC_LOCATION = "loc_"  # subscribe: location push
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

# Temperature isn't part of any known TSL model (see
# __init__._find_temperature_prop's synthetic fallback), so there's no
# generic way to know its local-LAN TTLV field id — it has to be confirmed
# per product by observing real device traffic. Confirmed via
# landbook-ha#27 diagnostics: field id 21 on productKey p11vkW (OmniBreeze
# DC2313R) reported a TYPE_NUMBER value matching the device's display
# exactly. Deliberately scoped by product key rather than assumed
# universal — an untested product's id 21 could mean something else
# entirely.
LOCAL_TEMPERATURE_IDS = {"p11vkW": 21}
