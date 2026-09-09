"""Tests for diagnostics output and credential redaction."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.landbook.diagnostics import (
    REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.landbook.const import DOMAIN


@pytest.fixture()
def hass_with_entry():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "diag_entry"
    entry.data = {
        "bearer_token": "secret_token",
        "refresh_token": "secret_refresh",
        "email": "user@example.com",
        "password": "hunter2",
        "uid": "user_123",
        "device_key": "dk1",
        "product_key": "pk1",
        "region": "us",
        "device_name": "Living Room Fan",
        "product_name": "OmniBreeze",
        "fw_version": "2.1.0",
    }
    entry.options = {"temperature_unit": "°F"}

    mqtt_client = MagicMock()
    mqtt_client._connected = True

    hass.data = {
        DOMAIN: {
            "diag_entry": {
                "device_id": "qdpk1dk1",
                "pk": "pk1",
                "dk": "dk1",
                "uid": "user_123",
                "online": True,
                "power_prop": {"code": "power"},
                "speed_prop": {"code": "speed"},
                "mode_prop": {"code": "mode"},
                "oscillation_prop": None,
                "countdown_prop": None,
                "temperature_prop": {"code": "temperature"},
                "light_props": [{"code": "light"}],
                "extra_props": [{"code": "sound"}],
                "state": {"power": True, "speed": 6},
            },
            "_accounts": {
                "user_123": {
                    "client": mqtt_client,
                    "entries": {"diag_entry"},
                },
            },
        },
    }
    return hass, entry


@pytest.mark.asyncio
async def test_diagnostics_output_shape(hass_with_entry):
    hass, entry = hass_with_entry
    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "config_entry" in result
    assert "device" in result
    assert "tsl_props" in result
    assert "current_state" in result
    assert "mqtt" in result


@pytest.mark.asyncio
async def test_credentials_redacted(hass_with_entry):
    hass, entry = hass_with_entry
    result = await async_get_config_entry_diagnostics(hass, entry)

    config = result["config_entry"]
    assert config.get("bearer_token") != "secret_token"
    assert config.get("refresh_token") != "secret_refresh"
    assert config.get("email") != "user@example.com"
    assert config.get("password") != "hunter2"
    assert config.get("uid") != "user_123"


@pytest.mark.asyncio
async def test_non_sensitive_fields_present(hass_with_entry):
    hass, entry = hass_with_entry
    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["device"]["device_id"] == "qdpk1dk1"
    assert result["device"]["online"] is True
    assert result["device"]["fw_version"] == "2.1.0"
    assert result["tsl_props"]["power"] == "power"
    assert result["tsl_props"]["lights"] == ["light"]
    assert result["current_state"]["power"] is True
    assert result["mqtt"]["connected"] is True
    assert "diag_entry" in result["mqtt"]["shared_devices"]


@pytest.mark.asyncio
async def test_redact_set_covers_all_secrets():
    expected = {"bearer_token", "refresh_token", "email", "password", "uid"}
    assert REDACT == expected
