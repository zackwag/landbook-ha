"""Diagnostics support for Landbook."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BEARER_TOKEN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_UID,
    DOMAIN,
)

REDACT = {CONF_BEARER_TOKEN, CONF_REFRESH_TOKEN, CONF_EMAIL, CONF_PASSWORD, CONF_UID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id, {})
    accounts = domain_data.get("_accounts", {})
    uid = entry_data.get("uid")
    account = accounts.get(uid, {})
    mqtt_client = account.get("client")

    # Collect prop codes for each detected role
    def _prop_code(p: dict | None) -> str | None:
        return p["code"] if p else None

    return {
        "config_entry": async_redact_data(dict(entry.data), REDACT),
        "options": dict(entry.options),
        "device": {
            "device_id": entry_data.get("device_id"),
            "pk": entry_data.get("pk"),
            "dk": entry_data.get("dk"),
            "online": entry_data.get("online"),
            "fw_version": entry.data.get("fw_version"),
        },
        "tsl_props": {
            "power": _prop_code(entry_data.get("power_prop")),
            "speed": _prop_code(entry_data.get("speed_prop")),
            "mode": _prop_code(entry_data.get("mode_prop")),
            "oscillation": _prop_code(entry_data.get("oscillation_prop")),
            "countdown": _prop_code(entry_data.get("countdown_prop")),
            "temperature": _prop_code(entry_data.get("temperature_prop")),
            "lights": [p["code"] for p in (entry_data.get("light_props") or [])],
            "extra": [p["code"] for p in (entry_data.get("extra_props") or [])],
        },
        "current_state": dict(entry_data.get("state", {})),
        "mqtt": {
            "connected": mqtt_client._connected if mqtt_client else None,
            "shared_devices": list(account.get("entries", [])),
        },
    }
