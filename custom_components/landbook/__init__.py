"""Landbook integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .api import LandbookAPIError, LandbookAuthError, async_get_device_attributes, async_get_tsl, async_refresh_token, refresh_token
from .const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_FW_VERSION,
    CONF_PRODUCT_KEY,
    CONF_REGION,
    CONF_SIGNAL_STRENGTH,
    CONF_UID,
    DEFAULT_REGION,
    DISPLAY_LIGHT_HINTS,
    DOMAIN,
    REGIONS,
    SIGNAL_STRENGTH_POLL_INTERVAL,
    TEMPERATURE_NAME_HINTS,
    OSCILLATION_NAME_HINTS,
    POWER_SORT_ORDER,
    SPEED_NAME_HINTS,
)
from .mqtt_client import LandbookMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["diagnostics", "fan", "light", "number", "select", "sensor", "switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Landbook from a config entry."""
    bearer_token: str = entry.data[CONF_BEARER_TOKEN]
    uid: str = entry.data[CONF_UID]
    pk: str = entry.data[CONF_PRODUCT_KEY]
    dk: str = entry.data[CONF_DEVICE_KEY]
    region: str = entry.data.get(CONF_REGION, DEFAULT_REGION)
    region_cfg = REGIONS.get(region, REGIONS[DEFAULT_REGION])
    device_id = f"qd{pk}{dk}"

    try:
        properties = await async_get_tsl(bearer_token, pk, region)
    except LandbookAPIError as exc:
        if "Token validation failed" in str(exc):
            try:
                bearer_token = await async_refresh_token(bearer_token, region)
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_BEARER_TOKEN: bearer_token}
                )
                properties = await async_get_tsl(bearer_token, pk, region)
            except LandbookAuthError as auth_exc:
                if "rejected" in str(auth_exc).lower():
                    entry.async_start_reauth(hass)
                raise ConfigEntryNotReady(f"Token expired and refresh failed: {auth_exc}") from auth_exc
            except LandbookAPIError as retry_exc:
                raise ConfigEntryNotReady(f"Could not fetch TSL model after token refresh: {retry_exc}") from retry_exc
        else:
            raise ConfigEntryNotReady(f"Could not fetch TSL model: {exc}") from exc

    power_prop        = _find_power_prop(properties)
    speed_prop        = _find_speed_prop(properties, power_prop)
    mode_prop         = _find_mode_prop(properties, power_prop, speed_prop)
    oscillation_prop  = _find_oscillation_prop(properties, power_prop, speed_prop, mode_prop)

    claimed = {id(p) for p in [power_prop, speed_prop, mode_prop, oscillation_prop] if p}
    light_props = _find_light_props(properties, claimed)
    claimed |= {id(p) for p in light_props}
    temperature_prop = _find_temperature_prop(properties, claimed)
    if temperature_prop and not temperature_prop.get("synthetic"):
        claimed.add(id(temperature_prop))
    countdown_prop = _find_countdown_prop(properties, claimed)
    if countdown_prop:
        claimed.add(id(countdown_prop))
    extra_props = [p for p in properties if id(p) not in claimed]

    domain_data = hass.data.setdefault(DOMAIN, {})
    accounts = domain_data.setdefault("_accounts", {})

    if uid not in accounts:
        # First device for this account — create the shared MQTT client
        def _token_refresher() -> str:
            # Read the latest token from any entry for this account so we never
            # refresh using a stale token after a previous successful refresh
            current_token = bearer_token
            for eid in list(accounts.get(uid, {}).get("entries", set())):
                cfg_entry = hass.config_entries.async_get_entry(eid)
                if cfg_entry:
                    current_token = cfg_entry.data.get(CONF_BEARER_TOKEN, bearer_token)
                    break
            try:
                new_token = refresh_token(current_token, region)
            except LandbookAuthError as exc:
                _LOGGER.warning("Token rejected for %s, triggering reauth: %s", uid, exc)
                for eid in list(accounts.get(uid, {}).get("entries", set())):
                    cfg_entry = hass.config_entries.async_get_entry(eid)
                    if cfg_entry:
                        hass.loop.call_soon_threadsafe(
                            hass.async_create_task,
                            _async_trigger_reauth(hass, cfg_entry),
                        )
                raise
            except Exception as exc:
                _LOGGER.warning("Token refresh failed for %s (network?), will retry: %s", uid, exc)
                raise
            hass.loop.call_soon_threadsafe(
                hass.async_create_task,
                _async_persist_token_for_account(hass, uid, new_token),
            )
            return new_token

        mqtt_client = LandbookMQTTClient(
            uid, bearer_token,
            mqtt_host=region_cfg["mqtt_host"],
            token_refresher=_token_refresher,
        )
        try:
            await hass.async_add_executor_job(mqtt_client.connect)
        except ConnectionError as exc:
            raise ConfigEntryNotReady(f"MQTT connection failed: {exc}") from exc

        accounts[uid] = {"client": mqtt_client, "entries": set()}
        _LOGGER.info("Landbook: shared MQTT connection established for account %s", uid)
    else:
        mqtt_client = accounts[uid]["client"]
        _LOGGER.debug("Landbook: reusing shared MQTT connection for account %s", uid)

    accounts[uid]["entries"].add(entry.entry_id)

    domain_data[entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "device_id": device_id,
        "pk": pk,
        "dk": dk,
        "power_prop": power_prop,
        "speed_prop": speed_prop,
        "mode_prop": mode_prop,
        "oscillation_prop": oscillation_prop,
        "countdown_prop": countdown_prop,
        "extra_props": extra_props,
        "light_props": light_props,
        "temperature_prop": temperature_prop,
        "state": {},
        "online": True,
        "uid": uid,
        "all_codes": [p["code"] for p in properties],
    }

    def _mqtt_callback(suffix: str, payload: Any) -> None:
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if entry_data is None:
            return

        if suffix == "bus_":
            data_block = payload.get("data", payload)
            kv = data_block.get("kv", {})
            changed_keys: set[str] = set()
            if isinstance(kv, dict):
                entry_data["state"].update(kv)
                changed_keys = set(kv.keys())
            elif isinstance(kv, list):
                for item in kv:
                    entry_data["state"].update(item)
                    changed_keys.update(item.keys())
            if changed_keys:
                hass.loop.call_soon_threadsafe(
                    hass.async_create_task,
                    _async_update_entities(hass, entry.entry_id, changed_keys),
                )

        elif suffix == "ack_":
            if payload.get("status") != "succ":
                _LOGGER.warning("Command ack failed for %s: %s", dk, payload)

        elif suffix == "onl_":
            _LOGGER.debug("onl_ raw payload for %s: %s", dk, payload)
            status = (
                payload.get("data", {}).get("value")
                if isinstance(payload.get("data"), dict)
                else payload.get("status")
                or payload.get("online")
                or payload.get("connectStatus")
            )
            if status is not None:
                online = bool(status)
                if entry_data["online"] != online:
                    entry_data["online"] = online
                    _LOGGER.info("Landbook device %s went %s", dk, "online" if online else "offline")
                    hass.loop.call_soon_threadsafe(
                        hass.async_create_task,
                        _async_update_entities(hass, entry.entry_id, None),
                    )
            else:
                _LOGGER.warning("onl_ payload for %s had no recognised status key: %s", dk, payload)

    mqtt_client.subscribe_device(device_id, _mqtt_callback)

    # On (re)connect, request state for ALL devices on this account
    def _request_all_states() -> None:
        for eid, edata in hass.data.get(DOMAIN, {}).items():
            if eid == "_accounts" or not isinstance(edata, dict):
                continue
            if edata.get("uid") == uid:
                mqtt_client.send_read(
                    edata["device_id"], edata["pk"], edata["dk"], edata["all_codes"]
                )

    mqtt_client._on_reconnect = _request_all_states
    mqtt_client.send_read(device_id, pk, dk, [p["code"] for p in properties])

    # Also seed initial state from REST API as a fallback
    try:
        attrs = await async_get_device_attributes(bearer_token, pk, dk, region)
        _LOGGER.debug("getDeviceBusinessAttributes raw response for %s: %s", dk, attrs)

        # Extract firmware version from deviceData and persist to entry
        device_data = (attrs if isinstance(attrs, dict) else {}).get("deviceData") or {}
        fw_version = device_data.get("version")
        if fw_version and entry.data.get(CONF_FW_VERSION) != fw_version:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_FW_VERSION: fw_version}
            )

        # Seed property state from customizeTslInfo list, coercing string values
        # to native types so entity handlers see the same types as MQTT bus_ messages
        prop_types = {p["code"]: p["dataType"] for p in properties}
        tsl_info = (attrs if isinstance(attrs, dict) else {}).get("customizeTslInfo") or attrs
        initial_state: dict = {}
        if isinstance(tsl_info, list):
            for item in tsl_info:
                code = item.get("resourceCode") or item.get("code")
                val = item.get("resourceValce") or item.get("value")
                if code is not None:
                    initial_state[code] = _coerce_value(val, prop_types.get(code))
        elif isinstance(tsl_info, dict):
            initial_state = tsl_info
        _LOGGER.debug("Initial state seeded for %s: %s", dk, initial_state)
        hass.data[DOMAIN][entry.entry_id]["state"] = initial_state
    except LandbookAPIError as exc:
        _LOGGER.warning("Could not fetch initial device attributes for %s: %s", dk, exc)

    # Start signal strength polling if the option is enabled
    _setup_signal_polling(hass, entry, bearer_token, pk, dk, region)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when options change so temperature unit takes effect immediately
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _setup_signal_polling(
    hass: HomeAssistant,
    entry: ConfigEntry,
    bearer_token: str,
    pk: str,
    dk: str,
    region: str,
) -> None:
    """Register a periodic poll for signal strength if the option is enabled."""
    enabled = entry.options.get(
        CONF_SIGNAL_STRENGTH,
        entry.data.get(CONF_SIGNAL_STRENGTH, False),
    )
    if not enabled:
        return

    async def _poll(_now: object = None) -> None:
        try:
            current_token = entry.data.get(CONF_BEARER_TOKEN, bearer_token)
            attrs = await async_get_device_attributes(current_token, pk, dk, region)
            device_data = (attrs if isinstance(attrs, dict) else {}).get("deviceData") or {}
            rssi = device_data.get("signalStrength")
            if rssi is not None:
                entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
                if entry_data is not None:
                    entry_data["signal_strength"] = int(rssi)
                    await _async_update_entities(hass, entry.entry_id, {"signal_strength"})
        except Exception as exc:
            _LOGGER.debug("Signal strength poll failed for %s: %s", dk, exc)

    # Poll immediately then on interval
    hass.async_create_task(_poll())
    cancel = async_track_time_interval(
        hass, _poll, timedelta(seconds=SIGNAL_STRENGTH_POLL_INTERVAL)
    )
    entry.async_on_unload(cancel)


def _coerce_value(val: object, data_type: str | None) -> object:
    """Coerce a string value from the REST API to the native type used by MQTT."""
    if val is None:
        return val
    if data_type == "BOOL":
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"
    if data_type == "INT":
        try:
            return int(val)
        except (ValueError, TypeError):
            return val
    if data_type == "ENUM":
        try:
            return int(val)
        except (ValueError, TypeError):
            return val
    return val


async def _async_trigger_reauth(hass: HomeAssistant, entry: ConfigEntry) -> None:
    entry.async_start_reauth(hass)


async def _async_persist_token_for_account(hass: HomeAssistant, uid: str, token: str) -> None:
    """Persist a refreshed token to all config entries for this account."""
    accounts = hass.data.get(DOMAIN, {}).get("_accounts", {})
    for eid in list(accounts.get(uid, {}).get("entries", set())):
        cfg_entry = hass.config_entries.async_get_entry(eid)
        if cfg_entry:
            hass.config_entries.async_update_entry(
                cfg_entry, data={**cfg_entry.data, CONF_BEARER_TOKEN: token}
            )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        entry_data = domain_data.pop(entry.entry_id, {})
        uid = entry_data.get("uid")
        accounts = domain_data.get("_accounts", {})
        if uid and uid in accounts:
            accounts[uid]["entries"].discard(entry.entry_id)
            if not accounts[uid]["entries"]:
                # Last device for this account — disconnect
                client: LandbookMQTTClient = accounts[uid]["client"]
                await hass.async_add_executor_job(client.disconnect)
                del accounts[uid]
                _LOGGER.info("Landbook: shared MQTT connection closed for account %s", uid)
    return unload_ok


async def _async_update_entities(hass: HomeAssistant, entry_id: str, changed_keys: set[str] | None = None) -> None:
    hass.bus.async_fire(f"{DOMAIN}_state_update_{entry_id}", {"changed_keys": changed_keys or set()})


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
    """Find the INT speed property (used for percentage control)."""
    for p in properties:
        if p is power_prop:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "INT" and any(
            hint in name_lower or hint in code_lower
            for hint in SPEED_NAME_HINTS
        ):
            return p
    return None


def _find_mode_prop(
    properties: list[dict], power_prop: dict | None, speed_prop: dict | None
) -> dict | None:
    """Find the ENUM mode property (used for preset modes)."""
    for p in properties:
        if p is power_prop or p is speed_prop:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "ENUM" and any(
            hint in name_lower or hint in code_lower
            for hint in ("mode", "working")
        ):
            return p
    return None


def _find_oscillation_prop(
    properties: list[dict],
    power_prop: dict | None,
    speed_prop: dict | None,
    mode_prop: dict | None = None,
) -> dict | None:
    for p in properties:
        if p is power_prop or p is speed_prop or p is mode_prop:
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


def _find_countdown_prop(
    properties: list[dict], claimed_ids: set
) -> dict | None:
    """Find a countdown/timer ENUM property."""
    for p in properties:
        if id(p) in claimed_ids:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "ENUM" and any(
            hint in name_lower or hint in code_lower
            for hint in ("countdown", "timer", "timing")
        ):
            return p
    return None
