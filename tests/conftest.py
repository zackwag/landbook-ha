"""Shared fixtures for Landbook integration tests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def mock_landbook_api():
    """Patch landbook_api callables and return them as a namespace for easy access."""
    with (
        patch("custom_components.landbook.async_get_tsl", new_callable=AsyncMock) as mock_tsl,
        patch("custom_components.landbook.async_refresh_token", new_callable=AsyncMock) as mock_async_refresh,
        patch("custom_components.landbook.refresh_token") as mock_sync_refresh,
        patch("custom_components.landbook.async_get_device_attributes", new_callable=AsyncMock) as mock_attrs,
        patch("custom_components.landbook.LandbookMQTTClient") as mock_mqtt_cls,
    ):
        mock_mqtt = MagicMock()
        mock_mqtt.connect = MagicMock()
        mock_mqtt.disconnect = MagicMock()
        mock_mqtt.subscribe_device = MagicMock()
        mock_mqtt.send_read = MagicMock()
        mock_mqtt_cls.return_value = mock_mqtt

        mock_tsl.return_value = [
            {"code": "power", "name": "Power", "dataType": "BOOL", "sort": 0,
             "specs": [{"name": "On", "value": "true"}, {"name": "Off", "value": "false"}]},
            {"code": "speed", "name": "Speed", "dataType": "INT", "sort": 1,
             "specs": {"min": "1", "max": "12", "step": "1"}},
        ]
        mock_attrs.return_value = {"customizeTslInfo": [], "deviceData": {}}

        yield SimpleNamespace(
            async_get_tsl=mock_tsl,
            async_refresh_token=mock_async_refresh,
            refresh_token=mock_sync_refresh,
            async_get_device_attributes=mock_attrs,
            mqtt_cls=mock_mqtt_cls,
            mqtt=mock_mqtt,
        )


def make_config_entry(
    hass,
    entry_id="entry_1",
    uid="user_1",
    bearer_token="old_access",
    refresh_token="old_refresh",
):
    """Create a mock ConfigEntry and register it with hass."""
    data = {
        "bearer_token": bearer_token,
        "refresh_token": refresh_token,
        "uid": uid,
        "product_key": "pk1",
        "device_key": "dk1",
        "region": "us",
        "device_name": "Test Fan",
        "product_name": "Test Product",
    }
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = dict(data)
    entry.options = {}
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    entry.async_on_unload = MagicMock()
    entry.async_start_reauth = MagicMock()
    return entry


def make_hass():
    """Create a minimal mock HomeAssistant object."""
    hass = MagicMock()
    hass.data = {}
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()

    entries_by_id = {}

    def _async_get_entry(eid):
        return entries_by_id.get(eid)

    def _async_entries(domain):
        return list(entries_by_id.values())

    def _async_update_entry(entry, *, data=None, **kwargs):
        if data is not None:
            entry.data = dict(data)

    hass.config_entries = MagicMock()
    hass.config_entries.async_get_entry = _async_get_entry
    hass.config_entries.async_entries = _async_entries
    hass.config_entries.async_update_entry = _async_update_entry
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: fn(*a))
    hass.async_create_task = MagicMock(side_effect=lambda coro: asyncio.ensure_future(coro))

    hass._entries_by_id = entries_by_id
    return hass


def register_entry(hass, entry):
    """Register a mock config entry so hass.config_entries can find it."""
    hass._entries_by_id[entry.entry_id] = entry
