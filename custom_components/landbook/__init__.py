"""Landbook integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import LandbookAPIError, async_get_device_attributes, async_get_tsl
from .const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_PRODUCT_KEY,
    CONF_UID,
    DOMAIN,
    POWER_SORT_ORDER,
    SPEED_NAME_HINTS,
)
from .mqtt_client import LandbookMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan", "number", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Landbook from a config entry."""
    bearer_token: str = entry.data[CONF_BEARER_TOKEN]
    uid: str = entry.data[CONF_UID]
    pk: str = entry.data[CONF_PRODUCT_KEY]
    dk: str = entry.data[CONF_DEVICE_KEY]
    device_id = f"qd{pk}{dk}"

    # Fetch TSL (writable properties)
    try:
        properties = await async_get_tsl(bearer_token, pk)
    except LandbookAPIError as exc:
        raise ConfigEntryNotReady(f"Could not fetch TSL model: {exc}") from exc

    # Identify power switch
    power_prop = _find_power_prop(properties)

    # Identify speed property (used by FanEntity for percentage/preset)
    speed_prop = _find_speed_prop(properties, power_prop)

    # All other writable props become number/select helpers
    extra_props = [
        p for p in properties
        if p is not power_prop and p is not speed_prop
    ]

    # Build MQTT client
    mqtt_client = LandbookMQTTClient(uid, bearer_token)
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
        "extra_props": extra_props,
        # Shared state dict — entities write optimistic state here,
        # MQTT ack callbacks update it authoritatively.
        "state": {},
    }

    # Wire MQTT messages into shared state
    def _mqtt_callback(suffix: str, payload: Any) -> None:
        if suffix in ("ack_", "bus_"):
            kv = payload.get("kv")
            if isinstance(kv, list):
                for item in kv:
                    hass.data[DOMAIN][entry.entry_id]["state"].update(item)
                hass.async_create_task(
                    _async_update_entities(hass, entry.entry_id)
                )

    mqtt_client.subscribe_device(device_id, _mqtt_callback)

    # Seed initial state so entities have values before first MQTT push
    try:
        attrs = await async_get_device_attributes(bearer_token, pk, dk)
        # attrs is a list of {code, value} dicts
        initial_state: dict = {}
        if isinstance(attrs, list):
            for item in attrs:
                code = item.get("code")
                val = item.get("value")
                if code is not None:
                    initial_state[code] = val
        elif isinstance(attrs, dict):
            initial_state = attrs
        hass.data[DOMAIN][entry.entry_id]["state"] = initial_state
    except LandbookAPIError:
        _LOGGER.warning("Could not fetch initial device attributes for %s", dk)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        mqtt_client: LandbookMQTTClient | None = data.get("mqtt_client")
        if mqtt_client:
            await hass.async_add_executor_job(mqtt_client.disconnect)
    return unload_ok


async def _async_update_entities(hass: HomeAssistant, entry_id: str) -> None:
    """Signal all entities for this entry to refresh from shared state."""
    hass.bus.async_fire(f"{DOMAIN}_state_update_{entry_id}")


# ---------------------------------------------------------------------------
# TSL helpers
# ---------------------------------------------------------------------------

def _find_power_prop(properties: list[dict]) -> dict | None:
    """Find the main on/off BOOL property (sort=0 with on/open/enable spec)."""
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
    # Fallback: first BOOL property
    return next((p for p in properties if p["dataType"] == "BOOL"), None)


def _find_speed_prop(
    properties: list[dict], power_prop: dict | None
) -> dict | None:
    """Find an INT or ENUM property that looks like a speed/level control."""
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
