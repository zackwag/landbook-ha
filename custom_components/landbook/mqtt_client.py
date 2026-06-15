"""Landbook MQTT client — WebSocket/TLS connection, pub/sub."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from .const import MQTT_HOST, MQTT_KEEPALIVE, MQTT_PORT, MQTT_WS_PATH

_LOGGER = logging.getLogger(__name__)


class LandbookMQTTClient:
    """Manages a single persistent MQTT connection for one account."""

    def __init__(self, uid: str, bearer_token: str) -> None:
        self._uid = uid
        self._bearer_token = bearer_token
        self._client: mqtt.Client | None = None
        self._connected = False
        self._msg_counter = 1000

        # device_id -> list of callbacks
        self._listeners: dict[str, list[Callable[[str, Any], None]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish the WebSocket/TLS MQTT connection (blocking until connected or timeout)."""
        client_id = f"qu_{self._uid}_{int(time.time() * 1000)}"
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311,
        )
        client.ws_set_options(path=MQTT_WS_PATH)
        client.tls_set()
        client.username_pw_set("", self._bearer_token)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        client.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        client.loop_start()
        self._client = client

        for _ in range(40):
            if self._connected:
                break
            time.sleep(0.25)

        if not self._connected:
            raise ConnectionError("MQTT connection timed out")

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False

    def subscribe_device(
        self,
        device_id: str,
        callback: Callable[[str, Any], None],
    ) -> None:
        """Subscribe to all topics for a device and register a callback.

        callback(topic_suffix, payload_dict)
        """
        if device_id not in self._listeners:
            self._listeners[device_id] = []
            if self._client and self._connected:
                self._subscribe_topics(device_id)

        self._listeners[device_id].append(callback)

    def send_write(self, device_id: str, pk: str, dk: str, props: dict) -> None:
        """Publish a WRITE-ATTR command."""
        if not self._client or not self._connected:
            raise ConnectionError("MQTT not connected")

        self._msg_counter = (self._msg_counter + 1) & 0xFFFF
        payload = json.dumps(
            {
                "msgId": self._msg_counter,
                "productKey": pk,
                "deviceKey": dk,
                "type": "WRITE-ATTR",
                "kv": json.dumps([props]),
                "cacheTime": 0,
                "isCache": False,
                "isCover": False,
            }
        )
        self._client.publish(f"q/1/d/{device_id}/sys_", payload, qos=1)
        _LOGGER.debug("send_write device=%s props=%s", device_id, props)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _subscribe_topics(self, device_id: str) -> None:
        assert self._client
        # Subscribe to all known downstream topics for this device
        for suffix in ("ack_", "bus_", "onl_", "ota_", "inf_", "loc_"):
            self._client.subscribe(f"q/2/d/{device_id}/{suffix}", qos=1)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if str(reason_code) in ("Success", "0") or reason_code == 0:
            self._connected = True
            for device_id in self._listeners:
                self._subscribe_topics(device_id)
            _LOGGER.info("Landbook MQTT connected")
        else:
            _LOGGER.error("Landbook MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self._connected = False
        _LOGGER.warning("Landbook MQTT disconnected: %s", reason_code)

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        parts = msg.topic.split("/")
        # topic format: q/2/d/{device_id}/{suffix}
        if len(parts) < 5:
            return
        device_id = parts[3]
        suffix = parts[4]

        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            _LOGGER.debug("Non-JSON MQTT payload on %s", msg.topic)
            return

        _LOGGER.debug("MQTT [%s] %s: %s", device_id, suffix, payload)

        for cb in self._listeners.get(device_id, []):
            try:
                cb(suffix, payload)
            except Exception:
                _LOGGER.exception("Error in MQTT listener for %s", device_id)
