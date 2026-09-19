"""Tests for local-LAN control wiring: _connect_local_client,
_make_send_command, and _make_local_state_handler in __init__.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from landbook_api.local_client import DiscoveredDevice
from landbook_api.local_protocol import TYPE_BOOL_TRUE, TYPE_BYTES, TYPE_NUMBER, TTLVField

from custom_components.landbook import (
    _connect_local_client,
    _make_local_state_handler,
    _make_send_command,
)
from custom_components.landbook.const import CONF_AUTH_KEY, DOMAIN

from .conftest import make_config_entry, make_hass, register_entry


def _account(local_devices=None, local_clients=None):
    return {
        "local_devices": local_devices,
        "local_clients": local_clients if local_clients is not None else {},
    }


class TestConnectLocalClient:
    @pytest.mark.asyncio
    async def test_missing_auth_key_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)  # no CONF_AUTH_KEY in data
        accounts = {"u1": _account()}
        lock = asyncio.Lock()

        result = await _connect_local_client(hass, entry, accounts, lock, "u1", "pk1", "dk1")

        assert result is None
        mock_landbook_api.discover_devices.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_not_found_via_discovery_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.return_value = []  # nothing found

        result = await _connect_local_client(hass, entry, accounts, lock, "u1", "pk1", "dk1")

        assert result is None
        mock_landbook_api.local_client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_connect_returns_client(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]

        result = await _connect_local_client(hass, entry, accounts, lock, "u1", "pk1", "dk1")

        assert result is mock_landbook_api.local_client
        mock_landbook_api.local_client_cls.assert_called_once_with(
            "pk1", "dk1", "dGVzdGtleQ==", "10.0.0.5", 6607
        )
        mock_landbook_api.local_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        mock_landbook_api.local_client.connect.side_effect = ConnectionError("login rejected")

        result = await _connect_local_client(hass, entry, accounts, lock, "u1", "pk1", "dk1")

        assert result is None

    @pytest.mark.asyncio
    async def test_discovery_only_runs_once_per_account(self, mock_landbook_api):
        hass = make_hass()
        entry1 = make_config_entry(hass, entry_id="e1")
        entry1.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        entry2 = make_config_entry(hass, entry_id="e2")
        entry2.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]

        await _connect_local_client(hass, entry1, accounts, lock, "u1", "pk1", "dk1")
        await _connect_local_client(hass, entry2, accounts, lock, "u1", "pk1", "dk1")

        mock_landbook_api.discover_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_failure_caches_empty_and_does_not_retry(self, mock_landbook_api):
        hass = make_hass()
        entry1 = make_config_entry(hass, entry_id="e1")
        entry1.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        entry2 = make_config_entry(hass, entry_id="e2")
        entry2.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.side_effect = OSError("no route to host")

        r1 = await _connect_local_client(hass, entry1, accounts, lock, "u1", "pk1", "dk1")
        r2 = await _connect_local_client(hass, entry2, accounts, lock, "u1", "pk1", "dk1")

        assert r1 is None
        assert r2 is None
        assert accounts["u1"]["local_devices"] == {}
        mock_landbook_api.discover_devices.assert_called_once()


class TestMakeSendCommand:
    def _entry_data(self, local_client=None):
        return {
            "mqtt_client": MagicMock(),
            "local_client": local_client,
            "properties": [
                {"code": "power", "id": 1, "dataType": "BOOL"},
                {"code": "speed", "id": 3, "dataType": "INT"},
            ],
            "device_id": "qdpk1dk1",
            "pk": "pk1",
            "dk": "dk1",
        }

    def test_no_local_client_uses_cloud(self):
        hass = make_hass()
        entry_data = self._entry_data(local_client=None)
        hass.data[DOMAIN] = {"e1": entry_data}

        send_command = _make_send_command(hass, "e1")
        send_command({"power": True})

        entry_data["mqtt_client"].send_write.assert_called_once_with(
            "qdpk1dk1", "pk1", "dk1", {"power": True}
        )

    def test_local_client_present_uses_local_not_cloud(self):
        hass = make_hass()
        local_client = MagicMock()
        entry_data = self._entry_data(local_client=local_client)
        hass.data[DOMAIN] = {"e1": entry_data}

        send_command = _make_send_command(hass, "e1")
        send_command({"power": True, "speed": 3})

        local_client.write.assert_called_once()
        fields = local_client.write.call_args[0][0]
        # Bool fields encode their value in the TTLV *type*, not a value
        # byte (see local_protocol.field_for_property) — the power field's
        # value is expected to be None, not True.
        assert {(f.id, f.type, f.value) for f in fields} == {
            (1, TYPE_BOOL_TRUE, None),
            (3, TYPE_NUMBER, 3),
        }
        entry_data["mqtt_client"].send_write.assert_not_called()

    def test_local_write_failure_falls_back_to_cloud(self):
        hass = make_hass()
        local_client = MagicMock()
        local_client.write.side_effect = OSError("connection reset")
        entry_data = self._entry_data(local_client=local_client)
        hass.data[DOMAIN] = {"e1": entry_data}

        send_command = _make_send_command(hass, "e1")
        send_command({"power": False})

        entry_data["mqtt_client"].send_write.assert_called_once_with(
            "qdpk1dk1", "pk1", "dk1", {"power": False}
        )

    def test_prop_without_id_skipped_for_local_falls_back_to_cloud(self):
        hass = make_hass()
        local_client = MagicMock()
        entry_data = self._entry_data(local_client=local_client)
        entry_data["properties"] = [{"code": "power", "dataType": "BOOL"}]  # no "id"
        hass.data[DOMAIN] = {"e1": entry_data}

        send_command = _make_send_command(hass, "e1")
        send_command({"power": True})

        local_client.write.assert_not_called()
        entry_data["mqtt_client"].send_write.assert_called_once_with(
            "qdpk1dk1", "pk1", "dk1", {"power": True}
        )

    def test_missing_entry_data_is_a_noop(self):
        hass = make_hass()
        hass.data[DOMAIN] = {}
        send_command = _make_send_command(hass, "missing")
        send_command({"power": True})  # must not raise


class TestSetupEntryWithLocalControlEnabled:
    @pytest.mark.asyncio
    async def test_local_client_connected_and_used_for_writes(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        # The shared conftest TSL fixture has no "id" field (it predates
        # local control) — real productTSL responses do, so give this
        # end-to-end test properties that actually let a local write happen.
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        entry.data["local_control_enabled"] = True
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client

        entry_data["send_command"]({"power": True})
        api.local_client.write.assert_called_once()
        api.mqtt.send_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_by_default_uses_cloud_only(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is None
        api.discover_devices.assert_not_called()

        entry_data["send_command"]({"power": True})
        api.mqtt.send_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_update_wired_and_initial_read_sent(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        entry.data["local_control_enabled"] = True
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        # Best-effort initial read, matching the protocol (see module note:
        # this is a nudge, not load-bearing — devices self-report anyway).
        api.local_client.read.assert_called_once_with([1])

        # on_update wired so a device push actually updates HA state,
        # through the same state dict / event mechanism cloud MQTT uses.
        assert callable(api.local_client.on_update)
        api.local_client.on_update([TTLVField(1, TYPE_BOOL_TRUE, True)])

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["state"]["power"] is True

    @pytest.mark.asyncio
    async def test_disabled_local_control_never_sets_on_update(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        # local control never activated for this entry, so the local
        # client mock (which only gets touched inside the `if local_client
        # is not None` block) should never have been used at all.
        api.local_client.read.assert_not_called()
        assert hass.data[DOMAIN]["e1"]["local_client"] is None


class TestMakeLocalStateHandler:
    def test_updates_state_dict_and_schedules_event(self):
        hass = make_hass()
        entry_data = {"state": {}}
        hass.data[DOMAIN] = {"e1": entry_data}

        handler = _make_local_state_handler(hass, "e1", {1: "power", 3: "speed"})
        handler([TTLVField(1, TYPE_BOOL_TRUE, True), TTLVField(3, TYPE_NUMBER, 5)])

        assert entry_data["state"] == {"power": True, "speed": 5}
        hass.loop.call_soon_threadsafe.assert_called_once()

    def test_decodes_bytes_field_to_str(self):
        hass = make_hass()
        entry_data = {"state": {}}
        hass.data[DOMAIN] = {"e1": entry_data}

        handler = _make_local_state_handler(hass, "e1", {6: "some_text_prop"})
        handler([TTLVField(6, TYPE_BYTES, b"hello")])

        assert entry_data["state"]["some_text_prop"] == "hello"

    def test_unknown_field_id_ignored(self):
        hass = make_hass()
        entry_data = {"state": {}}
        hass.data[DOMAIN] = {"e1": entry_data}

        handler = _make_local_state_handler(hass, "e1", {1: "power"})
        handler([TTLVField(99, TYPE_NUMBER, 5)])

        assert entry_data["state"] == {}
        hass.loop.call_soon_threadsafe.assert_not_called()

    def test_missing_entry_data_is_a_noop(self):
        hass = make_hass()
        hass.data[DOMAIN] = {}

        handler = _make_local_state_handler(hass, "missing", {1: "power"})
        handler([TTLVField(1, TYPE_BOOL_TRUE, True)])  # must not raise
