"""Landbook integration."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from landbook_api import (
    DEFAULT_REGION,
    REGIONS,
    LandbookAPIError,
    LandbookAuthError,
    LandbookMQTTClient,
    async_get_device_attributes,
    async_get_device_list,
    async_get_tsl,
    async_refresh_token,
    refresh_token,
)
from landbook_api.local_client import LandbookLocalClient, discover_devices
from landbook_api.local_protocol import TYPE_BYTES, field_for_property

from .const import (
    CONF_AUTH_KEY,
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_FW_VERSION,
    CONF_MQTT_WATCHDOG_ENABLED,
    CONF_PRODUCT_KEY,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SIGNAL_STRENGTH,
    CONF_TSL_CACHE,
    CONF_UID,
    DISPLAY_LIGHT_HINTS,
    DOMAIN,
    LOCAL_CONNECT_TIMEOUT,
    LOCAL_DISCOVERY_TIMEOUT,
    LOCAL_TEMPERATURE_IDS,
    MQTT_WATCHDOG_CHECK_INTERVAL,
    MQTT_WATCHDOG_STALE_INTERVAL,
    OSCILLATION_NAME_HINTS,
    POWER_SORT_ORDER,
    PROACTIVE_TOKEN_REFRESH_INTERVAL,
    SIGNAL_STRENGTH_POLL_INTERVAL,
    SPEED_NAME_HINTS,
    TEMPERATURE_NAME_HINTS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["fan", "light", "number", "select", "sensor", "switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Landbook from a config entry."""
    bearer_token: str = entry.data[CONF_BEARER_TOKEN]
    # Entries created before the refresh-token fix have no refresh token on file.
    # They can't be silently upgraded — the old access token alone can't obtain
    # one — so treat that case the same as a rejected refresh: ask for reauth.
    refresh_tok: str = entry.data.get(CONF_REFRESH_TOKEN, "")
    uid: str = entry.data[CONF_UID]
    pk: str = entry.data[CONF_PRODUCT_KEY]
    dk: str = entry.data[CONF_DEVICE_KEY]
    region: str = entry.data.get(CONF_REGION, DEFAULT_REGION)
    region_cfg = REGIONS.get(region, REGIONS[DEFAULT_REGION])
    device_id = f"qd{pk}{dk}"

    # Every device on one account keeps its own copy of a *single-use* refresh
    # token. On a cold boot Home Assistant sets up all of the account's config
    # entries concurrently, so without serialization each entry would call
    # async_refresh_token() with the same token — the first rotates it and the
    # rest get "Token refresh rejected" and a spurious reauth (issue #9). The
    # runtime _refresh_lock below only covers the proactive-timer / MQTT-reconnect
    # path, not this setup-time path.
    #
    # Serialize the setup-time token check/refresh per account: the first entry
    # refreshes and persists the new pair to every entry for the account; the
    # others wait on the lock, re-read the now-fresh token from their entry, and
    # skip the refresh entirely.
    domain_data = hass.data.setdefault(DOMAIN, {})
    setup_locks = domain_data.setdefault("_setup_locks", {})
    setup_lock = setup_locks.get(uid)
    if setup_lock is None:
        setup_lock = setup_locks[uid] = asyncio.Lock()

    account_tokens = domain_data.setdefault("_account_tokens", {})
    reauth_fired_key = f"_reauth_fired_{uid}"

    async with setup_lock:
        # A sibling entry may have refreshed while we waited — prefer the
        # in-memory store (updated synchronously under the lock) over config
        # entries (updated asynchronously and may lag).
        stored = account_tokens.get(uid, {})
        bearer_token = stored.get("access") or entry.data.get(CONF_BEARER_TOKEN, bearer_token)
        refresh_tok = stored.get("refresh") or entry.data.get(CONF_REFRESH_TOKEN, refresh_tok)

        # TSL rarely changes, so a cached copy (see CONF_TSL_CACHE) skips
        # this REST call — and the token-refresh dance below that's only
        # ever triggered by it — on every restart after the first. Remove
        # and re-add the device to force a refresh if it ever does change.
        cached_properties = entry.data.get(CONF_TSL_CACHE)
        if cached_properties is not None:
            properties = cached_properties
        else:
            try:
                properties = await async_get_tsl(bearer_token, pk, region)
            except LandbookAPIError as exc:
                if "Token validation failed" not in str(exc):
                    raise ConfigEntryNotReady(f"Could not fetch TSL model: {exc}") from exc

                if domain_data.get(reauth_fired_key):
                    raise ConfigEntryNotReady(
                        f"Token invalid for {uid}, reauth already requested — will retry"
                    )

                if not refresh_tok:
                    domain_data[reauth_fired_key] = True
                    entry.async_start_reauth(hass)
                    raise ConfigEntryNotReady(
                        "Token expired and no refresh token on file (pre-upgrade entry) — reauth required"
                    )
                try:
                    bearer_token, refresh_tok = await async_refresh_token(
                        bearer_token, refresh_tok, region
                    )
                    account_tokens[uid] = {"access": bearer_token, "refresh": refresh_tok}
                    for cfg_entry in hass.config_entries.async_entries(DOMAIN):
                        if cfg_entry.data.get(CONF_UID) == uid:
                            hass.config_entries.async_update_entry(
                                cfg_entry,
                                data={
                                    **cfg_entry.data,
                                    CONF_BEARER_TOKEN: bearer_token,
                                    CONF_REFRESH_TOKEN: refresh_tok,
                                },
                            )
                    properties = await async_get_tsl(bearer_token, pk, region)
                except LandbookAuthError as auth_exc:
                    if not domain_data.get(reauth_fired_key):
                        domain_data[reauth_fired_key] = True
                        if "rejected" in str(auth_exc).lower():
                            entry.async_start_reauth(hass)
                    raise ConfigEntryNotReady(
                        f"Token expired and refresh failed: {auth_exc}"
                    ) from auth_exc
                except LandbookAPIError as retry_exc:
                    raise ConfigEntryNotReady(
                        f"Could not fetch TSL model after token refresh: {retry_exc}"
                    ) from retry_exc

            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_TSL_CACHE: properties}
            )

    power_prop = _find_power_prop(properties)
    speed_prop = _find_speed_prop(properties, power_prop)
    mode_prop = _find_mode_prop(properties, power_prop, speed_prop)
    oscillation_prop = _find_oscillation_prop(properties, power_prop, speed_prop, mode_prop)

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

    accounts = domain_data.setdefault("_accounts", {})

    client_locks = domain_data.setdefault("_client_locks", {})
    client_lock = client_locks.get(uid)
    if client_lock is None:
        client_lock = client_locks[uid] = asyncio.Lock()

    async with client_lock:
        if uid not in accounts:
            # First device for this account — create the shared MQTT client
            _refresh_lock = threading.Lock()
            _latest_tokens = {"access": bearer_token, "refresh": refresh_tok}

            def _token_refresher() -> str:
                with _refresh_lock:
                    stored = account_tokens.get(uid, {})
                    current_token = stored.get("access") or _latest_tokens["access"]
                    current_refresh = stored.get("refresh") or _latest_tokens["refresh"]
                    try:
                        if not current_refresh:
                            raise LandbookAuthError(
                                "No refresh token on file (pre-upgrade entry) — reauth required"
                            )
                        new_token, new_refresh = refresh_token(
                            current_token, current_refresh, region
                        )
                    except LandbookAuthError as exc:
                        _LOGGER.warning("Token rejected for %s, triggering reauth: %s", uid, exc)
                        if accounts.get(uid, {}).get("client"):
                            accounts[uid]["client"].halt_reconnects()
                        if not domain_data.get(reauth_fired_key):
                            domain_data[reauth_fired_key] = True
                            entries = list(accounts.get(uid, {}).get("entries", set()))
                            if entries:
                                cfg_entry = hass.config_entries.async_get_entry(entries[0])
                                if cfg_entry:
                                    hass.loop.call_soon_threadsafe(
                                        hass.async_create_task,
                                        _async_trigger_reauth(hass, cfg_entry),
                                    )
                        raise
                    except Exception as exc:
                        _LOGGER.warning(
                            "Token refresh failed for %s (network?), will retry: %s", uid, exc
                        )
                        raise
                    _latest_tokens["access"] = new_token
                    _latest_tokens["refresh"] = new_refresh
                    # Keep the in-memory account store authoritative for the
                    # setup fast-path and the unload-time persist below.
                    account_tokens[uid] = {"access": new_token, "refresh": new_refresh}
                    hass.loop.call_soon_threadsafe(
                        hass.async_create_task,
                        _async_persist_token_for_account(hass, uid, new_token, new_refresh),
                    )
                    return new_token

            mqtt_client = LandbookMQTTClient(
                uid,
                bearer_token,
                mqtt_host=region_cfg["mqtt_host"],
                token_refresher=_token_refresher,
            )
            try:
                await hass.async_add_executor_job(mqtt_client.connect)
            except ConnectionError as exc:
                raise ConfigEntryNotReady(f"MQTT connection failed: {exc}") from exc

            async def _proactive_token_refresh(_now: object = None) -> None:
                try:
                    new_token = await hass.async_add_executor_job(_token_refresher)
                    mqtt_client.update_token(new_token)
                except Exception as exc:  # noqa: BLE001 — already logged/handled above
                    _LOGGER.debug("Proactive token refresh for %s did not succeed: %s", uid, exc)

            cancel_proactive_refresh = async_track_time_interval(
                hass, _proactive_token_refresh, timedelta(seconds=PROACTIVE_TOKEN_REFRESH_INTERVAL)
            )

            def _account_watchdog_enabled() -> bool:
                for eid in list(accounts.get(uid, {}).get("entries", set())):
                    cfg_entry = hass.config_entries.async_get_entry(eid)
                    if cfg_entry and cfg_entry.options.get(CONF_MQTT_WATCHDOG_ENABLED, True):
                        return True
                return False

            async def _mqtt_watchdog(_now: object = None) -> None:
                try:
                    if not _account_watchdog_enabled():
                        return
                    acct = accounts.get(uid)
                    last = acct.get("last_activity") if acct else None
                    if last is None:
                        return
                    if time.monotonic() - last > MQTT_WATCHDOG_STALE_INTERVAL:
                        _LOGGER.warning(
                            "Landbook: no MQTT message for account %s in %.0fs — forcing reconnect",
                            uid,
                            MQTT_WATCHDOG_STALE_INTERVAL,
                        )
                        await hass.async_add_executor_job(mqtt_client.reconnect)
                        if accounts.get(uid):
                            accounts[uid]["last_activity"] = time.monotonic()
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("MQTT watchdog for %s failed: %s", uid, exc)

            cancel_watchdog = async_track_time_interval(
                hass, _mqtt_watchdog, timedelta(seconds=MQTT_WATCHDOG_CHECK_INTERVAL)
            )

            accounts[uid] = {
                "client": mqtt_client,
                "entries": set(),
                "cancel_proactive_refresh": cancel_proactive_refresh,
                "cancel_watchdog": cancel_watchdog,
                "last_activity": time.monotonic(),
                # None = discovery not yet attempted for this account; {} =
                # attempted and found nothing (still valid, avoids retrying
                # every entry setup). Populated lazily by whichever entry
                # first wants local control — see _connect_local_client.
                "local_devices": None,
                "local_clients": {},
            }
            _LOGGER.info("Landbook: shared MQTT connection established for account %s", uid)
        else:
            mqtt_client = accounts[uid]["client"]
            _LOGGER.debug("Landbook: reusing shared MQTT connection for account %s", uid)

    accounts[uid]["entries"].add(entry.entry_id)

    # Local-LAN control is always attempted, no opt-in toggle — it's
    # already designed to degrade gracefully to cloud MQTT on any failure
    # (missing authKey, discovery timeout, connect/login rejection), which
    # is exactly what every entry already did before this existed. Given
    # cloud MQTT's own reliability problems (#27), attempting local
    # unconditionally is strictly safer than requiring someone to
    # discover and flip a setting to get it.
    local_client = await _connect_local_client(
        hass, entry, accounts, client_lock, uid, pk, dk, bearer_token, region
    )
    if local_client is not None:
        accounts[uid]["local_clients"][entry.entry_id] = local_client

    domain_data[entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "local_client": local_client,
        "properties": properties,
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
        # Codes local control actually reports on (populated below when
        # local_client is connected) — anything not in this set (e.g. a
        # synthetic property like temperature on an untested product, see
        # _find_temperature_prop) has no known local equivalent, so cloud
        # MQTT's bus_ reports for it must keep flowing even while local is
        # otherwise authoritative. See _mqtt_callback's bus_ branch below.
        "local_codes": set(),
    }
    domain_data[entry.entry_id]["send_command"] = _make_send_command(hass, entry.entry_id)

    if local_client is not None:
        id_to_code = {p["id"]: p["code"] for p in properties if "id" in p}
        # Temperature isn't in the TSL model, so it's never in `properties`
        # above — but for products where its local field id has been
        # confirmed (LOCAL_TEMPERATURE_IDS), map it too, so local control
        # covers it instead of depending on cloud's bus_ channel, which has
        # proven unreliable (#27). Guarded by `synthetic` so a product that
        # *does* have a real TSL temperature property (with its own id)
        # never gets silently overridden by this hardcoded one.
        temp_id = LOCAL_TEMPERATURE_IDS.get(pk)
        if temp_id is not None and temperature_prop and temperature_prop.get("synthetic"):
            id_to_code[temp_id] = "temperature"
        domain_data[entry.entry_id]["local_codes"] = set(id_to_code.values())
        local_client.on_update = _make_local_state_handler(hass, entry.entry_id, id_to_code)
        local_client.on_disconnect = _make_local_disconnect_handler(hass, entry.entry_id, uid, dk)
        # Best-effort nudge — on real hardware tested so far, a device
        # pushes its own properties continuously regardless of whether this
        # is called, so this mostly just matches the protocol rather than
        # being load-bearing. Never block/fail setup over it.
        try:
            local_client.read(list(id_to_code.keys()))
        except Exception as exc:  # noqa: BLE001 - best-effort, device still self-reports
            _LOGGER.debug("Landbook: initial local read for %s failed: %s", dk, exc)

    def _mqtt_callback(suffix: str, payload: Any) -> None:
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if entry_data is None:
            return

        accounts = hass.data.get(DOMAIN, {}).get("_accounts", {})
        if accounts.get(uid):
            accounts[uid]["last_activity"] = time.monotonic()

        if suffix == "bus_":
            # Local control is authoritative for any code it reports on
            # (see _make_local_state_handler) — cloud MQTT's bus_ channel
            # has had intermittent reliability problems (#27), and blending
            # both would let a stale or delayed cloud update silently
            # overwrite a correct local one. But not every code has a local
            # equivalent — e.g. temperature is often a synthetic property
            # absent from the TSL model entirely (_find_temperature_prop)
            # and only ever arrives via cloud — so only codes local control
            # actually covers (entry_data["local_codes"]) are dropped here;
            # everything else still updates from cloud same as always.
            local_codes = entry_data.get("local_codes") or set()
            data_block = payload.get("data", payload)
            kv = data_block.get("kv", {})
            if isinstance(kv, dict):
                items = [kv]
            elif isinstance(kv, list):
                items = kv
            else:
                items = []
            changed_keys: set[str] = set()
            for item in items:
                for code, value in item.items():
                    if code in local_codes:
                        continue
                    entry_data["state"][code] = value
                    changed_keys.add(code)
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
                else payload.get("status") or payload.get("online") or payload.get("connectStatus")
            )
            if status is not None:
                online = bool(status)
                if entry_data["online"] != online:
                    entry_data["online"] = online
                    _LOGGER.info(
                        "Landbook device %s went %s", dk, "online" if online else "offline"
                    )
                    hass.loop.call_soon_threadsafe(
                        hass.async_create_task,
                        _async_update_entities(hass, entry.entry_id, None),
                    )
            else:
                _LOGGER.warning("onl_ payload for %s had no recognised status key: %s", dk, payload)

    mqtt_client.subscribe_device(device_id, _mqtt_callback)

    # On (re)connect, request state for ALL devices on this account, except
    # ones a live local-LAN connection is already keeping fresh — asking
    # cloud to re-read those is both pointless (local reads are authoritative
    # for them, see _mqtt_callback's bus_ branch) and, on real hardware,
    # reliably fails its SENDACK once the device has gone mostly quiet on
    # cloud in favor of local.
    def _request_all_states() -> None:
        for eid, edata in hass.data.get(DOMAIN, {}).items():
            if eid.startswith("_") or not isinstance(edata, dict):
                continue
            if edata.get("uid") == uid and edata.get("local_client") is None:
                mqtt_client.send_read(
                    edata["device_id"], edata["pk"], edata["dk"], edata["all_codes"]
                )

    mqtt_client._on_reconnect = _request_all_states
    if local_client is None:
        # Same rationale as _request_all_states above — pointless and
        # failure-prone to ask cloud to read a device local control is
        # already connected to.
        mqtt_client.send_read(device_id, pk, dk, [p["code"] for p in properties])

    # Also seed initial state from REST API as a fallback — but only if
    # local control doesn't already cover every property the device has
    # (temperature included). When it does, this call is pure overhead:
    # local already reports everything within about a second of connecting
    # (see PR #49), so there's nothing left for cloud to seed. The one
    # thing this call also does — refreshing CONF_FW_VERSION for the
    # Device info panel — stops updating in that case too; that's cosmetic
    # only (not read by any functional code path) and acceptable in
    # exchange for skipping a REST call every single restart.
    needed_codes = {p["code"] for p in properties}
    if temperature_prop and temperature_prop.get("synthetic"):
        needed_codes.add("temperature")
    local_codes = hass.data[DOMAIN][entry.entry_id].get("local_codes") or set()
    if local_client is None or not needed_codes <= local_codes:
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
            # Merge rather than replace, and skip codes local control already
            # covers (entry_data["local_codes"]) — this REST snapshot can be
            # stale for a device that's mostly quiet on cloud in favor of local
            # (see PR #47's temperature fix for the same class of issue), and
            # replacing outright could stomp a correct value local already
            # pushed (or is about to) with a stale cloud one, e.g. showing a
            # fan that's actually on as off after a restart.
            hass.data[DOMAIN][entry.entry_id]["state"].update(
                {code: value for code, value in initial_state.items() if code not in local_codes}
            )
        except LandbookAPIError as exc:
            _LOGGER.warning("Could not fetch initial device attributes for %s: %s", dk, exc)
    else:
        _LOGGER.debug(
            "Landbook: skipping REST state seed for %s — local control covers every property",
            dk,
        )

    # Start signal strength polling if the option is enabled
    _setup_signal_polling(hass, entry, bearer_token, pk, dk, region)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when options change so temperature unit takes effect immediately
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _backfill_auth_key(
    hass: HomeAssistant,
    entry: ConfigEntry,
    bearer_token: str,
    region: str,
    pk: str,
    dk: str,
) -> str | None:
    """Fetch and persist the authKey for an entry that predates it being
    stored unconditionally at setup (#41). The device list is the only
    place Landbook's API ever returns it — there's no way to look up a
    single already-paired device's authKey directly — so existing users
    would otherwise need to remove and re-add the device just to pick one
    up. Best-effort: any failure here just means local control stays
    unavailable for this device, same as if it had no authKey at all.
    """
    try:
        devices = await async_get_device_list(bearer_token, region)
    except Exception as exc:  # noqa: BLE001 - best-effort, must not break setup
        _LOGGER.debug("Landbook: authKey backfill fetch failed for %s: %s", dk, exc)
        return None

    device = next(
        (d for d in devices if d.get("productKey") == pk and d.get("deviceKey") == dk),
        None,
    )
    auth_key = (device or {}).get("authKey")
    if not auth_key:
        return None

    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_AUTH_KEY: auth_key})
    _LOGGER.info("Landbook: backfilled authKey for %s — local control now available", dk)
    return auth_key


async def _connect_local_client(
    hass: HomeAssistant,
    entry: ConfigEntry,
    accounts: dict,
    client_lock: asyncio.Lock,
    uid: str,
    pk: str,
    dk: str,
    bearer_token: str,
    region: str,
) -> LandbookLocalClient | None:
    """Best-effort attempt to establish local-LAN control for one device.

    Always attempted, no opt-in toggle — but must never block or break entry
    setup, so any failure here (missing authKey, discovery timeout,
    connect/login failure) just logs a warning and returns None, leaving the
    caller to fall back to the always-available cloud MQTT path.
    """
    auth_key = entry.data.get(CONF_AUTH_KEY)
    if not auth_key:
        auth_key = await _backfill_auth_key(hass, entry, bearer_token, region, pk, dk)
        if not auth_key:
            _LOGGER.warning(
                "Landbook: no authKey on file for %s and none found via device list "
                "— using cloud MQTT",
                dk,
            )
            return None

    # Discovery is a broadcast + listen, shared once per account rather than
    # repeated per device — see the "local_devices" cache comment where
    # accounts[uid] is created.
    async with client_lock:
        if accounts[uid]["local_devices"] is None:
            try:
                discovered = await hass.async_add_executor_job(
                    discover_devices, LOCAL_DISCOVERY_TIMEOUT
                )
                accounts[uid]["local_devices"] = {
                    (d.product_key, d.device_key): d for d in discovered
                }
            except Exception as exc:  # noqa: BLE001 - discovery must not break setup
                _LOGGER.warning("Landbook: local discovery failed for account %s: %s", uid, exc)
                accounts[uid]["local_devices"] = {}
        match = accounts[uid]["local_devices"].get((pk, dk))

    if match is None:
        _LOGGER.warning(
            "Landbook: %s not found via LAN discovery — using cloud MQTT",
            dk,
        )
        return None

    local_client = LandbookLocalClient(pk, dk, auth_key, match.ip, match.port)
    try:
        await hass.async_add_executor_job(local_client.connect, LOCAL_CONNECT_TIMEOUT)
    except ConnectionError as exc:
        _LOGGER.warning(
            "Landbook: local control connect failed for %s (%s) — using cloud MQTT", dk, exc
        )
        return None

    _LOGGER.info("Landbook: local control connected for %s", dk)
    return local_client


def _make_send_command(hass: HomeAssistant, entry_id: str):
    """Build the callable entities use to issue a write, replacing direct
    self._data["mqtt_client"].send_write(...) calls. Prefers the local
    connection when one is up for this device; any failure there (or its
    absence) falls back to the shared cloud MQTT client, matching the
    always-on cloud behavior every entry had before local control existed.
    """

    def _send_command(props: dict) -> None:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is None:
            return

        local_client = entry_data.get("local_client")
        if local_client is not None:
            try:
                fields = [
                    field_for_property(p["id"], p["dataType"], props[p["code"]])
                    for p in entry_data["properties"]
                    if p["code"] in props and "id" in p
                ]
                if fields:
                    local_client.write(fields)
                    return
            except Exception as exc:  # noqa: BLE001 - fall back to cloud on any local failure
                _LOGGER.warning(
                    "Landbook: local write failed for %s (%s), falling back to cloud MQTT",
                    entry_data.get("dk"),
                    exc,
                )

        entry_data["mqtt_client"].send_write(
            entry_data["device_id"], entry_data["pk"], entry_data["dk"], props
        )

    return _send_command


def _make_local_state_handler(hass: HomeAssistant, entry_id: str, id_to_code: dict[int, str]):
    """Build the callback wired to LandbookLocalClient.on_update.

    Merges incoming property pushes into the same shared state dict and
    fires the same HA event that cloud MQTT's bus_ handler already
    feeds — so entities need no changes to benefit from this. Cloud MQTT's
    bus_ handler skips any code local control covers rather than blending
    (see _mqtt_callback), so this is now the *only* source for those codes
    while local is connected — which is exactly why losing the connection
    unexpectedly has to clear entry_data["local_client"] (see
    _make_local_disconnect_handler below), rather than leaving cloud
    silently starved of updates it thinks it should keep skipping.

    Called from LandbookLocalClient's background receive thread, like
    paho's MQTT callback — must marshal back onto the event loop via
    call_soon_threadsafe, same as _mqtt_callback below.
    """

    def _on_local_update(fields: list) -> None:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is None:
            return
        changed: set[str] = set()
        for f in fields:
            code = id_to_code.get(f.id)
            if code is None:
                continue
            value = f.value
            if f.type == TYPE_BYTES and isinstance(value, (bytes, bytearray)):
                # Match cloud MQTT's string representation for TEXT properties.
                value = value.decode("utf-8", errors="replace")
            entry_data["state"][code] = value
            changed.add(code)
        if changed:
            hass.loop.call_soon_threadsafe(
                hass.async_create_task,
                _async_update_entities(hass, entry_id, changed),
            )

    return _on_local_update


def _make_local_disconnect_handler(hass: HomeAssistant, entry_id: str, uid: str, dk: str):
    """Build the callback wired to LandbookLocalClient.on_disconnect.

    Local control has no auto-reconnect of its own yet, so once the
    connection drops unexpectedly there's nothing to wait for — clear
    entry_data["local_client"] (and the account-level local_clients entry)
    so every local-vs-cloud fork in this module (_make_send_command,
    _mqtt_callback's bus_ skip, the cloud read-request skips) immediately
    treats this device as cloud-only again, instead of silently starving
    on a dead reference until the next full HA restart.

    This does NOT touch entry_data["online"] — a dead local socket doesn't
    mean the device itself is offline (it could just be a local network
    hiccup between HA and the device specifically), so cloud MQTT's onl_
    event stays the sole source of truth for that.

    Called from LandbookLocalClient's background receive thread, like
    on_update — but unlike on_update, this needs no call_soon_threadsafe,
    since it only mutates plain dict/set state and fires no HA event.
    """

    def _on_local_disconnect() -> None:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is None or entry_data.get("local_client") is None:
            return
        _LOGGER.warning(
            "Landbook: local connection to %s lost unexpectedly — "
            "falling back to cloud MQTT for the rest of this session",
            dk,
        )
        entry_data["local_client"] = None
        entry_data["local_codes"] = set()
        accounts = hass.data.get(DOMAIN, {}).get("_accounts", {})
        acct = accounts.get(uid)
        if acct is not None:
            acct["local_clients"].pop(entry_id, None)

    return _on_local_disconnect


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if entry.state is not ConfigEntryState.LOADED:
        # A failed_unload / setup_error entry must not be reloaded — reload
        # raises OperationNotAllowed on an entry that isn't LOADED. Each
        # token persist fires the options listener for every sibling entry
        # on the account, so without this guard a broken entry spams
        # OperationNotAllowed on every refresh.
        return
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
        except Exception as exc:  # noqa: BLE001 - optional background poll, must not crash the entry
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


async def _async_persist_token_for_account(
    hass: HomeAssistant, uid: str, token: str, refresh_tok: str
) -> None:
    """Persist a refreshed access/refresh token pair to all config entries for this account."""
    accounts = hass.data.get(DOMAIN, {}).get("_accounts", {})
    for eid in list(accounts.get(uid, {}).get("entries", set())):
        cfg_entry = hass.config_entries.async_get_entry(eid)
        if cfg_entry:
            hass.config_entries.async_update_entry(
                cfg_entry,
                data={**cfg_entry.data, CONF_BEARER_TOKEN: token, CONF_REFRESH_TOKEN: refresh_tok},
            )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        entry_data = domain_data.pop(entry.entry_id, {})
        uid = entry_data.get("uid")
        accounts = domain_data.get("_accounts", {})
        acct = accounts.get(uid) if uid else None

        # Local connections are per-device, unlike the shared account MQTT
        # client below — disconnect this entry's own regardless of whether
        # it's the last entry on the account.
        local_client = entry_data.get("local_client")
        if local_client is not None:
            await hass.async_add_executor_job(local_client.disconnect)
        if acct is not None:
            acct.get("local_clients", {}).pop(entry.entry_id, None)

        if acct is not None:
            acct["entries"].discard(entry.entry_id)
            if not acct["entries"]:
                # Last device for this account — persist the account's latest
                # token pair before tearing down. The runtime refresher persists
                # rotations fire-and-forget; on a reboot or reload that task may
                # never land, leaving entry.data with the previous (burned)
                # refresh token and forcing a reauth at the next boot.
                latest_tokens = domain_data.get("_account_tokens", {}).get(uid)
                if latest_tokens and latest_tokens.get("refresh"):
                    try:
                        for cfg_entry in hass.config_entries.async_entries(DOMAIN):
                            if cfg_entry.data.get(CONF_UID) == uid:
                                hass.config_entries.async_update_entry(
                                    cfg_entry,
                                    data={
                                        **cfg_entry.data,
                                        CONF_BEARER_TOKEN: latest_tokens["access"],
                                        CONF_REFRESH_TOKEN: latest_tokens["refresh"],
                                    },
                                )
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.warning(
                            "Landbook: could not persist latest token for %s on unload: %s",
                            uid,
                            exc,
                        )

                client: LandbookMQTTClient = acct["client"]
                await hass.async_add_executor_job(client.disconnect)
                cancel_proactive_refresh = acct.get("cancel_proactive_refresh")
                if cancel_proactive_refresh:
                    cancel_proactive_refresh()
                cancel_watchdog = acct.get("cancel_watchdog")
                if cancel_watchdog:
                    cancel_watchdog()
                accounts.pop(uid, None)
                domain_data.get("_setup_locks", {}).pop(uid, None)
                domain_data.get("_client_locks", {}).pop(uid, None)
                domain_data.get("_account_tokens", {}).pop(uid, None)
                domain_data.pop(f"_reauth_fired_{uid}", None)
                _LOGGER.info("Landbook: shared MQTT connection closed for account %s", uid)
    return unload_ok


async def _async_update_entities(
    hass: HomeAssistant, entry_id: str, changed_keys: set[str] | None = None
) -> None:
    hass.bus.async_fire(
        f"{DOMAIN}_state_update_{entry_id}", {"changed_keys": changed_keys or set()}
    )


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


def _find_speed_prop(properties: list[dict], power_prop: dict | None) -> dict | None:
    """Find the INT speed property (used for percentage control)."""
    for p in properties:
        if p is power_prop:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "INT" and any(
            hint in name_lower or hint in code_lower for hint in SPEED_NAME_HINTS
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
            hint in name_lower or hint in code_lower for hint in ("mode", "working")
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
            hint in name_lower or hint in code_lower for hint in OSCILLATION_NAME_HINTS
        ):
            return p
    return None


def _find_light_props(properties: list[dict], claimed_ids: set) -> list[dict]:
    """Find BOOL properties that should be light entities (display/backlight)."""
    return [
        p
        for p in properties
        if id(p) not in claimed_ids
        and p["dataType"] == "BOOL"
        and any(
            hint in p.get("name", "").lower() or hint in p.get("code", "").lower()
            for hint in DISPLAY_LIGHT_HINTS
        )
    ]


def _find_temperature_prop(properties: list[dict], claimed_ids: set) -> dict | None:
    """Find a temperature property from the TSL or return a virtual one for bus_ reports."""
    for p in properties:
        if id(p) in claimed_ids:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if any(hint in name_lower or hint in code_lower for hint in TEMPERATURE_NAME_HINTS):
            return p
    # Temperature may not be in the writable TSL but still arrive in bus_ reports
    # Return a synthetic prop so the sensor entity knows to watch for it
    return {"code": "temperature", "name": "Temperature", "dataType": "INT", "synthetic": True}


def _find_countdown_prop(properties: list[dict], claimed_ids: set) -> dict | None:
    """Find a countdown/timer ENUM property."""
    for p in properties:
        if id(p) in claimed_ids:
            continue
        name_lower = p.get("name", "").lower()
        code_lower = p.get("code", "").lower()
        if p["dataType"] == "ENUM" and any(
            hint in name_lower or hint in code_lower for hint in ("countdown", "timer", "timing")
        ):
            return p
    return None
