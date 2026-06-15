"""Landbook integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import LandbookAPIError, LandbookAuthError, async_get_device_attributes, async_get_tsl, refresh_token
from .const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_PRODUCT_KEY,
    CONF_UID,
    DISPLAY_LIGHT_HINTS,
    DOMAIN,
    TEMPERATURE_NAME_HINTS,
    OSCILLATION_NAME_HINTS,
    POWER_SORT_ORDER,
    SPEED_NAME_HINTS,
)
from .mqtt_client import LandbookMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan", "light", "number", "select", "sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Landbook from a config entry."""
    bearer_token: str = entry.data[CONF_BEARER_TOKEN]
    uid: str = entry.data[CONF_UID]
    pk: str = entry.data[CONF_PRODUCT_KEY]
    dk: str = entry.data[CONF_DEVICE_KEY]
    device_id = f"qd{pk}{dk}"

    try:
        properties = await async_get_tsl(bearer_token, pk)
    except LandbookAPIError as exc:
        raise ConfigEntryNotReady(f"Could not fetch TSL model: {exc}") from exc

    power_prop        = _find_power_prop(properties)
    speed_prop        = _find_speed_prop(properties, power_prop)
    oscillation_prop  = _find_oscillation_prop(properties, power_prop, speed_prop)

    claimed = {id(p) for p in [power_prop, speed_prop, oscillation_prop] if p}
    light_props = _find_light_props(properties, claimed)
    claimed |= {id(p) for p in light_props}
    temperature_prop = _find_temperature_prop(properties, claimed)
    if temperature_prop and not temperature_prop.get("synthetic"):
        claimed.add(id(temperature_prop))
    extra_props = [p for p in properties if id(p) not in claimed]

    def _token_refresher() -> str:
        return refresh_token(bearer_token)

    mqtt_client = LandbookMQTTClient(uid, bearer_token, token_refresher=_token_refresher)
    try:
        await hass.async_add_executor_job(mqtt_client.connect)
    except ConnectionError as exc:
        raise ConfigEntryNotReady(f"MQTT connection failed: {exc}") from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "device_id": device_id,
        "pk": pk,
        "dk": dk,
        "bearer_token": bearer_token,
        "power_prop": power_prop,
        "speed_prop": speed_prop,
        "oscillation_prop": oscillation_prop,
        "extra_props": extra_props,
        "light_props": light_props,
        "temperature_prop": temperature_prop,
        "state": {},
        "online": True,  # optimistic until we get an onl_ message
    }

    def _mqtt_callback(suffix: str, payload: Any) -> None:
        entry_data = hass.data[DOMAIN][entry.entry_id]

        if suffix == "bus_":
            # kv is nested under data.kv in bus_ reports
            data_block = payload.get("data", payload)
            kv = data_block.get("kv", {})
            if isinstance(kv, dict):
                entry_data["state"].update(kv)
                hass.async_create_task(
                    _async_update_entities(hass, entry.entry_id)
                )
            elif isinstance(kv, list):
                for item in kv:
                    entry_data["state"].update(item)
                hass.async_create_task(
                    _async_update_entities(hass, entry.entry_id)
                )

        elif suffix == "ack_":
            if payload.get("status") != "succ":
                _LOGGER.warning("Command ack failed for %s: %s", dk, payload)

        elif suffix == "onl_":
            # Log the raw payload so we can confirm the shape
            _LOGGER.debug("onl_ raw payload for %s: %s", dk, payload)
            # Quectel shape: {"type":"ONLINE","data":{"value":1}}
            # value=1 means online, value=0 means offline
            status = (
                payload.get("data", {}).get("value")
                if isinstance(payload.get("data"), dict)
                else payload.get("status")
                or payload.get("online")
                or payload.get("connectStatus")
            )
            if status is not None:
                # Treat any truthy value as online
                online = bool(status)
                if entry_data["online"] != online:
                    entry_data["online"] = online
                    _LOGGER.info(
                        "Landbook device %s went %s",
                        dk,
                        "online" if online else "offline",
                    )
                    hass.async_create_task(
                        _async_update_entities(hass, entry.entry_id)
                    )
            else:
                _LOGGER.warning(
                    "onl_ payload for %s had no recognised status key: %s",
                    dk, payload
                )

    mqtt_client.subscribe_device(device_id, _mqtt_callback)

    # Seed initial state
    try:
        attrs = await async_get_device_attributes(bearer_token, pk, dk)
        _LOGGER.debug("getDeviceBusinessAttributes raw response for %s: %s", dk, attrs)
        initial_state: dict = {}
        if isinstance(attrs, list):
            for item in attrs:
                code = item.get("code")
                val = item.get("value")
                if code is not None:
                    initial_state[code] = val
        elif isinstance(attrs, dict):
            initial_state = attrs
        _LOGGER.debug("Initial state seeded for %s: %s", dk, initial_state)
        hass.data[DOMAIN][entry.entry_id]["state"] = initial_state
    except LandbookAPIError as exc:
        _LOGGER.warning("Could not fetch initial device attributes for %s: %s", dk, exc)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        mqtt_client: LandbookMQTTClient | None = data.get("mqtt_client")
        if mqtt_client:
            await hass.async_add_executor_job(mqtt_client.disconnect)
    return unload_ok


async def _async_update_entities(hass: HomeAssistant, entry_id: str) -> None:
    hass.bus.async_fire(f"{DOMAIN}_state_update_{entry_id}")


# ---------------------------------------------------------------------------
# TSL helpers
# ---------------------------------------------------------------------------

def _find_power_prop(properties: list[dict]) -> dict | None:
    for p in properties:
        if (
            p["dataType"] == "BOOL"
            and p.get("sort", 99) == POWER_SORT_ORDER
            and any(
                s.get("name", "").lower() in ("on", "open", "enable")
                for s in (p.get("specs") or [])
                if s.get("value") == "true"
            )
        ):
            return p
    return next((p for p in properties if p["dataType"] == "BOOL"), None)


def _find_speed_prop(
    properties: list[dict], power_prop: dict | None
) -> dict | None:
    for p in properties:
        if p is power_prop:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] in ("INT", "ENUM") and any(
            hint in name_lower or hint in code_lower
            for hint in SPEED_NAME_HINTS
        ):
            return p
    return None


def _find_oscillation_prop(
    properties: list[dict],
    power_prop: dict | None,
    speed_prop: dict | None,
) -> dict | None:
    for p in properties:
        if p is power_prop or p is speed_prop:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "BOOL" and any(
            hint in name_lower or hint in code_lower
            for hint in OSCILLATION_NAME_HINTS
        ):
            return p
    return None


def _find_light_props(
    properties: list[dict], claimed_ids: set
) -> list[dict]:
    """Find BOOL properties that should be light entities (display/backlight)."""
    return [
        p for p in properties
        if id(p) not in claimed_ids
        and p["dataType"] == "BOOL"
        and any(
            hint in p.get("name", "").lower() or hint in p.get("code", "").lower()
            for hint in DISPLAY_LIGHT_HINTS
        )
    ]


def _find_temperature_prop(
    properties: list[dict], claimed_ids: set
) -> dict | None:
    """Find a temperature property from the TSL or return a virtual one for bus_ reports."""
    for p in properties:
        if id(p) in claimed_ids:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if any(
            hint in name_lower or hint in code_lower
            for hint in TEMPERATURE_NAME_HINTS
        ):
            return p
    # Temperature may not be in the writable TSL but still arrive in bus_ reports
    # Return a synthetic prop so the sensor entity knows to watch for it
    return {"code": "temperature", "name": "Temperature", "dataType": "INT", "synthetic": True}
