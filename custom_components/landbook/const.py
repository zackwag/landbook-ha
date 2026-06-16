"""Constants for the Landbook integration."""

DOMAIN = "landbook"

# API
APP_ID = "584"
APP_VERSION = "3.6.0"
APP_SYSTEM_TYPE = "ios"

MQTT_PORT = 8443
MQTT_WS_PATH = "/ws/v2"
MQTT_KEEPALIVE = 40

# Region config key
CONF_REGION = "region"

# Region definitions — sourced from ad0.java (i=0 CN, i=1 EU, i=2 US)
REGIONS: dict[str, dict] = {
    "us": {
        "label": "United States",
        "api_base": "https://iot-api.quectelus.com",
        "mqtt_host": "iot-south.landecia.com",
        "user_domain": "U.SP.8589934603",
        "app_domain_key": "pUTp5goB1bLinprRQMmK3EPiiuPiGrJtKUNptWRXVmP",
    },
    "eu": {
        "label": "Europe",
        "api_base": "https://iot-api.quecteleu.com",
        "mqtt_host": "iot-south.quecteleu.com",
        "user_domain": "E.SP.4294967410",
        "app_domain_key": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
    },
    "cn": {
        "label": "China",
        "api_base": "https://iot-gateway.quectel.com",
        "mqtt_host": "iot-south.quectelcn.com",
        "user_domain": "C.DM.5903.1",
        "app_domain_key": "EufftRJSuWuVY7c6txzGifV9bJcfXHAFa7hXY5doXSn7",
    },
}

DEFAULT_REGION = "us"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BEARER_TOKEN = "bearer_token"
CONF_UID = "uid"
CONF_DEVICE_KEY = "device_key"
CONF_PRODUCT_KEY = "product_key"
CONF_DEVICE_NAME = "device_name"
CONF_PRODUCT_NAME = "product_name"
CONF_MUTE_ON_COMMAND = "mute_on_command"
CONF_FW_VERSION = "fw_version"
CONF_TEMP_UNIT = "temperature_unit"
TEMP_UNIT_F = "°F"
TEMP_UNIT_C = "°C"
CONF_SIGNAL_STRENGTH = "signal_strength_enabled"
SIGNAL_STRENGTH_POLL_INTERVAL = 300  # seconds

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
