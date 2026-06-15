"""Constants for the Landbook integration."""

DOMAIN = "landbook"

# API
APP_DOMAIN_KEY = "pUTp5goB1bLinprRQMmK3EPiiuPiGrJtKUNptWRXVmP"
APP_ID = "584"
APP_VERSION = "3.6.0"
APP_SYSTEM_TYPE = "ios"

API_BASE_URL = "https://iot-api.quectelus.com"
LOGIN_URL = API_BASE_URL + "/v2/enduser/enduserapi/emailPwdLogin"
REFRESH_TOKEN_URL = API_BASE_URL + "/v2/enduser/enduserapi/refreshToken"
PRODUCT_ATTRIBUTES_URL = API_BASE_URL + "/v2/binding/enduserapi/getDeviceBusinessAttributes"
MQTT_HOST = "iot-south.landecia.com"
MQTT_PORT = 8443
MQTT_WS_PATH = "/ws/v2"
MQTT_KEEPALIVE = 40

USER_DOMAIN = "U.SP.8589934603"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_BEARER_TOKEN = "bearer_token"
CONF_UID = "uid"
CONF_DEVICE_KEY = "device_key"
CONF_PRODUCT_KEY = "product_key"
CONF_DEVICE_NAME = "device_name"

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
