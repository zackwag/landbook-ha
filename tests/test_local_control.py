"""Tests for local-LAN control wiring: _connect_local_client,
_make_send_command, and _make_local_state_handler in __init__.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from landbook_api.local_client import DiscoveredDevice
from landbook_api.local_protocol import TYPE_BOOL_TRUE, TYPE_BYTES, TYPE_NUMBER, TTLVField

from custom_components.landbook import (
    _async_local_reconnect_loop,
    _connect_local_client,
    _make_local_disconnect_handler,
    _make_local_state_handler,
    _make_send_command,
    _wire_local_client,
)
from custom_components.landbook.const import (
    CONF_AUTH_KEY,
    CONF_DEVICE_KEY,
    CONF_PRODUCT_KEY,
    DOMAIN,
)

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

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

        assert result is None
        mock_landbook_api.discover_devices.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_auth_key_backfills_from_device_list_and_connects(
        self, mock_landbook_api
    ):
        """The exact regression this guards against: an entry created
        before authKey was stored unconditionally (#41) must not require
        removing and re-adding the device just to unlock local control —
        the device list has the authKey, so fetch and persist it there."""
        hass = make_hass()
        entry = make_config_entry(hass)  # no CONF_AUTH_KEY in data
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.async_get_device_list.return_value = [
            {"productKey": "pk1", "deviceKey": "dk1", "authKey": "dGVzdGtleQ=="}
        ]
        mock_landbook_api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

        assert result is mock_landbook_api.local_client
        mock_landbook_api.async_get_device_list.assert_called_once_with("tok", "us")
        assert entry.data[CONF_AUTH_KEY] == "dGVzdGtleQ=="

    @pytest.mark.asyncio
    async def test_backfill_finds_no_matching_device_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)  # no CONF_AUTH_KEY in data
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.async_get_device_list.return_value = [
            {"productKey": "pk_other", "deviceKey": "dk_other", "authKey": "irrelevant"}
        ]

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

        assert result is None
        assert CONF_AUTH_KEY not in entry.data
        mock_landbook_api.discover_devices.assert_not_called()

    @pytest.mark.asyncio
    async def test_backfill_fetch_failure_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)  # no CONF_AUTH_KEY in data
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.async_get_device_list.side_effect = RuntimeError("network error")

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_device_not_found_via_discovery_falls_back(self, mock_landbook_api):
        hass = make_hass()
        entry = make_config_entry(hass)
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        accounts = {"u1": _account()}
        lock = asyncio.Lock()
        mock_landbook_api.discover_devices.return_value = []  # nothing found

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

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

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

        assert result is mock_landbook_api.local_client
        mock_landbook_api.local_client_cls.assert_called_once_with(
            "pk1", "dk1", "dGVzdGtleQ==", "10.0.0.5", 6607
        )
        mock_landbook_api.local_client.connect.assert_called_once()
        mock_landbook_api.async_get_device_list.assert_not_called()

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

        result = await _connect_local_client(
            hass, entry, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

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

        await _connect_local_client(hass, entry1, accounts, lock, "u1", "pk1", "dk1", "tok", "us")
        await _connect_local_client(hass, entry2, accounts, lock, "u1", "pk1", "dk1", "tok", "us")

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

        r1 = await _connect_local_client(
            hass, entry1, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )
        r2 = await _connect_local_client(
            hass, entry2, accounts, lock, "u1", "pk1", "dk1", "tok", "us"
        )

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


class TestSetupEntryLocalControl:
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
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client

        entry_data["send_command"]({"power": True})
        api.local_client.write.assert_called_once()
        api.mqtt.send_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_auth_key_uses_cloud_only(self, mock_landbook_api):
        """Local control is always attempted, no opt-in toggle — but it
        still needs an authKey to log in, so entries without one (e.g. added
        before local control existed, or an API response that omitted it)
        fall back to cloud MQTT exactly as before."""
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
    async def test_on_disconnect_wired_and_clears_local_client_on_real_setup(
        self, mock_landbook_api
    ):
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
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client  # sanity check
        assert callable(api.local_client.on_disconnect)

        api.local_client.on_disconnect()

        assert entry_data["local_client"] is None
        assert entry_data["local_codes"] == set()
        assert "e1" not in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]

    @pytest.mark.asyncio
    async def test_no_local_client_never_touches_local_client_mock(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        # No authKey on this entry, so local control never connects, and
        # the local client mock (which only gets touched inside the `if
        # local_client is not None` block) should never have been used.
        api.local_client.read.assert_not_called()
        assert hass.data[DOMAIN]["e1"]["local_client"] is None

    @pytest.mark.asyncio
    async def test_initial_cloud_read_skipped_when_local_connected(self, mock_landbook_api):
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
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        assert hass.data[DOMAIN]["e1"]["local_client"] is api.local_client  # sanity check
        # Same rationale as _request_all_states: pointless and, on real
        # hardware, failure-prone to ask cloud to read a device local
        # control already connected to at setup.
        api.mqtt.send_read.assert_not_called()

    @pytest.mark.asyncio
    async def test_initial_cloud_read_sent_when_no_local_client(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api  # no authKey -> local control never connects

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        assert hass.data[DOMAIN]["e1"]["local_client"] is None  # sanity check
        api.mqtt.send_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_rest_seed_skips_codes_local_control_covers_but_seeds_others(
        self, mock_landbook_api
    ):
        """Regression test: the REST-based initial-state seed at the end of
        setup must not overwrite a code local control already owns — e.g. a
        stale cloud "off" clobbering a fan that's actually on after a
        restart — but should still seed codes local control has no way to
        report on at all, like a synthetic temperature property."""
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
        # Cloud's cached snapshot says the fan is off (stale) and also
        # reports a temperature that local control has no way to know
        # about (not in the TSL, so no local TTLV id for it).
        api.async_get_device_attributes.return_value = {
            "customizeTslInfo": [
                {"code": "power", "value": "false"},
                {"code": "temperature", "value": "77"},
            ],
            "deviceData": {},
        }

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client  # sanity check
        assert "power" not in entry_data["state"]  # not clobbered with stale "off"
        assert entry_data["state"]["temperature"] == "77"  # still seeded from cloud

    @pytest.mark.asyncio
    async def test_p11vkw_temperature_covered_by_confirmed_local_field_id(self, mock_landbook_api):
        """Regression test for the real-hardware finding behind this fix:
        on productKey p11vkW, field id 21 was confirmed (via landbook-ha#27
        diagnostics) to push temperature locally, matching the device's own
        display. It should be treated as local-covered like any other
        property, rather than depending on cloud's bus_ channel."""
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="p11vkW", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_PRODUCT_KEY] = "p11vkW"
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client  # sanity check
        assert "temperature" in entry_data["local_codes"]

        api.local_client.on_update([TTLVField(21, TYPE_NUMBER, 78)])
        assert entry_data["state"]["temperature"] == 78

    @pytest.mark.asyncio
    async def test_rest_state_seed_skipped_when_local_covers_everything(self, mock_landbook_api):
        """Once local control covers every property a device has — power
        plus the confirmed local temperature id on p11vkW — the REST
        device-attributes call is pure overhead and should be skipped."""
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="p11vkW", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_PRODUCT_KEY] = "p11vkW"
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        assert hass.data[DOMAIN]["e1"]["local_client"] is api.local_client  # sanity check
        api.async_get_device_attributes.assert_not_called()

    @pytest.mark.asyncio
    async def test_rest_state_seed_still_sent_when_local_missing_a_property(
        self, mock_landbook_api
    ):
        """Same product, but one TSL property has no local id — local
        control can't cover it, so the REST seed must still run."""
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="p11vkW", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
            {"code": "extra_no_id", "name": "Extra", "dataType": "BOOL", "sort": 99, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_PRODUCT_KEY] = "p11vkW"
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        assert hass.data[DOMAIN]["e1"]["local_client"] is api.local_client  # sanity check
        api.async_get_device_attributes.assert_called_once()


class TestMqttCallbackLocalFirst:
    """bus_ (cloud state report) handling inside _mqtt_callback, wired up
    through async_setup_entry, must defer to local control for codes it
    covers, but keep updating from cloud for codes it doesn't (e.g. a
    synthetic property like temperature that isn't in the TSL model at
    all — see __init__.py's _mqtt_callback bus_ branch for the rationale)."""

    async def _setup_with_local(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]
        # Needs an "id" so "power" ends up in entry_data["local_codes"] —
        # the default fixture TSL has no "id" field on any property.
        api.async_get_tsl.return_value = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []},
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is api.local_client  # sanity check
        assert entry_data["local_codes"] == {"power"}  # sanity check
        mqtt_callback = api.mqtt.subscribe_device.call_args[0][1]
        return hass, entry_data, mqtt_callback

    @pytest.mark.asyncio
    async def test_cloud_bus_ignored_for_codes_local_control_covers(self, mock_landbook_api):
        hass, entry_data, mqtt_callback = await self._setup_with_local(mock_landbook_api)
        hass.loop.call_soon_threadsafe.reset_mock()

        mqtt_callback("bus_", {"data": {"kv": {"power": True}}})

        assert "power" not in entry_data["state"]
        hass.loop.call_soon_threadsafe.assert_not_called()

    @pytest.mark.asyncio
    async def test_cloud_bus_still_processed_for_codes_local_control_does_not_cover(
        self, mock_landbook_api
    ):
        """Regression test: temperature (and anything else absent from the
        TSL model, see _find_temperature_prop) has no local TTLV id, so it
        can only ever arrive via cloud — it must keep updating even while
        local control is connected and authoritative for other codes."""
        hass, entry_data, mqtt_callback = await self._setup_with_local(mock_landbook_api)
        hass.loop.call_soon_threadsafe.reset_mock()

        mqtt_callback("bus_", {"data": {"kv": {"power": True, "temperature": "77"}}})

        assert "power" not in entry_data["state"]
        assert entry_data["state"]["temperature"] == "77"
        hass.loop.call_soon_threadsafe.assert_called_once()

    @pytest.mark.asyncio
    async def test_cloud_bus_processed_when_no_local_client(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api  # no authKey -> local control never connects

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        entry_data = hass.data[DOMAIN]["e1"]
        assert entry_data["local_client"] is None  # sanity check
        mqtt_callback = api.mqtt.subscribe_device.call_args[0][1]
        hass.loop.call_soon_threadsafe.reset_mock()

        mqtt_callback("bus_", {"data": {"kv": {"power": True}}})

        assert entry_data["state"]["power"] is True
        hass.loop.call_soon_threadsafe.assert_called_once()


class TestRequestAllStates:
    """The account-level reconnect handler (_request_all_states, wired as
    mqtt_client._on_reconnect) re-seeds state over cloud MQTT for every
    device on the account — except ones a live local-LAN connection is
    already keeping fresh, which would otherwise get a pointless cloud
    read that reliably fails its SENDACK on real hardware."""

    @pytest.mark.asyncio
    async def test_skips_local_connected_devices_but_reads_cloud_only_ones(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]

        local_entry = make_config_entry(hass, entry_id="e_local", uid="u1")
        local_entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, local_entry)

        cloud_entry = make_config_entry(hass, entry_id="e_cloud", uid="u1")
        cloud_entry.data[CONF_DEVICE_KEY] = "dk2"  # no authKey -> stays cloud-only
        register_entry(hass, cloud_entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, local_entry)
        await async_setup_entry(hass, cloud_entry)

        assert hass.data[DOMAIN]["e_local"]["local_client"] is api.local_client
        assert hass.data[DOMAIN]["e_cloud"]["local_client"] is None

        api.mqtt.send_read.reset_mock()
        api.mqtt._on_reconnect()

        called_device_ids = {c.args[0] for c in api.mqtt.send_read.call_args_list}
        assert called_device_ids == {"qdpk1dk2"}


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


class TestMakeLocalDisconnectHandler:
    def test_clears_local_client_and_local_codes(self):
        hass = make_hass()
        local_client = MagicMock()
        entry_data = {
            "local_client": local_client,
            "local_generation": 1,
            "local_codes": {"power", "speed"},
            "online": True,
        }
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {"local_clients": {"e1": local_client}}},
        }

        handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 1)
        handler()

        assert entry_data["local_client"] is None
        assert entry_data["local_codes"] == set()
        assert "e1" not in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]

    def test_does_not_touch_online_status(self):
        """A dead local socket doesn't mean the device itself is offline —
        cloud MQTT's onl_ event stays the sole source of truth for that."""
        hass = make_hass()
        entry_data = {
            "local_client": MagicMock(),
            "local_generation": 1,
            "local_codes": {"power"},
            "online": True,
        }
        hass.data[DOMAIN] = {"e1": entry_data, "_accounts": {"u1": {"local_clients": {}}}}

        handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 1)
        handler()

        assert entry_data["online"] is True

    def test_noop_when_local_client_already_none(self):
        """A clean, caller-initiated disconnect() never fires this
        callback (see landbook_api), but defend against a stray call
        anyway rather than assuming it can't happen."""
        hass = make_hass()
        entry_data = {
            "local_client": None,
            "local_generation": 0,
            "local_codes": set(),
            "online": True,
        }
        hass.data[DOMAIN] = {"e1": entry_data, "_accounts": {"u1": {"local_clients": {}}}}

        handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 0)
        handler()  # must not raise

    def test_missing_entry_data_is_a_noop(self):
        hass = make_hass()
        hass.data[DOMAIN] = {}

        handler = _make_local_disconnect_handler(hass, "missing", "u1", "pk1", "dk1", 1)
        handler()  # must not raise

    def test_missing_account_is_a_noop(self):
        """The account dict might already be gone (e.g. account-wide
        teardown mid-flight) — must not raise."""
        hass = make_hass()
        entry_data = {
            "local_client": MagicMock(),
            "local_generation": 1,
            "local_codes": {"power"},
            "online": True,
        }
        hass.data[DOMAIN] = {"e1": entry_data, "_accounts": {}}

        handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 1)
        handler()  # must not raise

        assert entry_data["local_client"] is None

    def test_stale_generation_is_a_noop(self):
        """A reconnect installs a new local_client with a higher
        generation — a stale on_disconnect from the old client's dying
        thread must not clear the new one."""
        hass = make_hass()
        new_client = MagicMock()
        entry_data = {
            "local_client": new_client,
            "local_generation": 2,
            "local_codes": {"power"},
            "online": True,
        }
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {"local_clients": {"e1": new_client}}},
        }

        old_handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 1)
        old_handler()

        assert entry_data["local_client"] is new_client
        assert entry_data["local_codes"] == {"power"}
        assert "e1" in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]


class TestWireLocalClient:
    def test_installs_callbacks_and_bumps_generation(self):
        hass = make_hass()
        local_client = MagicMock()
        entry_data = {
            "local_client": None,
            "local_generation": 0,
            "local_codes": set(),
            "properties": [
                {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL"},
            ],
            "temperature_prop": {"code": "temperature", "synthetic": True},
        }
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {"local_clients": {}}},
        }

        _wire_local_client(hass, "e1", "u1", "pk1", "dk1", local_client)

        assert entry_data["local_client"] is local_client
        assert entry_data["local_generation"] == 1
        assert "power" in entry_data["local_codes"]
        assert callable(local_client.on_update)
        assert callable(local_client.on_disconnect)
        assert "e1" in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]
        local_client.read.assert_called_once()

    def test_second_wire_bumps_generation_again(self):
        hass = make_hass()
        client1 = MagicMock()
        client2 = MagicMock()
        entry_data = {
            "local_client": None,
            "local_generation": 0,
            "local_codes": set(),
            "properties": [
                {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL"},
            ],
            "temperature_prop": None,
        }
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {"local_clients": {}}},
        }

        _wire_local_client(hass, "e1", "u1", "pk1", "dk1", client1)
        assert entry_data["local_generation"] == 1

        _wire_local_client(hass, "e1", "u1", "pk1", "dk1", client2)
        assert entry_data["local_generation"] == 2
        assert entry_data["local_client"] is client2

    def test_missing_entry_data_is_a_noop(self):
        hass = make_hass()
        hass.data[DOMAIN] = {}
        _wire_local_client(hass, "missing", "u1", "pk1", "dk1", MagicMock())


class TestAsyncLocalReconnectLoop:
    @pytest.mark.asyncio
    async def test_reconnects_on_cached_ip(self, mock_landbook_api):
        hass = make_hass()
        api = mock_landbook_api
        new_client = MagicMock()
        api.local_client_cls.return_value = new_client

        entry_data = {
            "local_client": None,
            "local_generation": 1,
            "local_codes": set(),
            "properties": [
                {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL"},
            ],
            "temperature_prop": None,
        }
        cached = DiscoveredDevice(
            product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
        )
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {
                "local_devices": {("pk1", "dk1"): cached},
                "local_clients": {},
            }},
            "_client_locks": {"u1": asyncio.Lock()},
        }

        # Patch asyncio.sleep so test doesn't actually wait
        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(hass, "e1", "u1", "pk1", "dk1", "auth123")
        finally:
            asyncio.sleep = original_sleep

        assert entry_data["local_client"] is new_client
        assert entry_data["local_generation"] == 2
        api.local_client_cls.assert_called_once_with("pk1", "dk1", "auth123", "10.0.0.5", 6607)

    @pytest.mark.asyncio
    async def test_exits_when_entry_data_gone(self, mock_landbook_api):
        hass = make_hass()
        hass.data[DOMAIN] = {}

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(hass, "e1", "u1", "pk1", "dk1", "auth123")
        finally:
            asyncio.sleep = original_sleep

        mock_landbook_api.local_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_exits_when_local_client_already_restored(self, mock_landbook_api):
        hass = make_hass()
        existing_client = MagicMock()
        entry_data = {
            "local_client": existing_client,
            "local_generation": 2,
            "local_codes": {"power"},
            "properties": [],
            "temperature_prop": None,
        }
        hass.data[DOMAIN] = {"e1": entry_data}

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(hass, "e1", "u1", "pk1", "dk1", "auth123")
        finally:
            asyncio.sleep = original_sleep

        assert entry_data["local_client"] is existing_client
        mock_landbook_api.local_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_discovery_after_cached_failures(self, mock_landbook_api):
        hass = make_hass()
        api = mock_landbook_api

        attempt = {"count": 0}
        new_client = MagicMock()

        def _connect_side_effect(timeout):
            attempt["count"] += 1
            if attempt["count"] <= 3:
                raise ConnectionError("refused")

        new_client.connect = MagicMock(side_effect=_connect_side_effect)
        api.local_client_cls.return_value = new_client

        cached = DiscoveredDevice(
            product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
        )
        fresh = DiscoveredDevice(
            product_key="pk1", device_key="dk1", ip="10.0.0.99", port=6607, version=1
        )
        api.discover_devices.return_value = [fresh]

        entry_data = {
            "local_client": None,
            "local_generation": 1,
            "local_codes": set(),
            "properties": [
                {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL"},
            ],
            "temperature_prop": None,
        }
        hass.data[DOMAIN] = {
            "e1": entry_data,
            "_accounts": {"u1": {
                "local_devices": {("pk1", "dk1"): cached},
                "local_clients": {},
            }},
            "_client_locks": {"u1": asyncio.Lock()},
        }

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(hass, "e1", "u1", "pk1", "dk1", "auth123")
        finally:
            asyncio.sleep = original_sleep

        assert entry_data["local_client"] is new_client
        # First 3 attempts used cached IP, 4th used fresh discovery IP
        calls = api.local_client_cls.call_args_list
        assert calls[-1].args[3] == "10.0.0.99"
        api.discover_devices.assert_called_once()


class TestThreeFanReconnect:
    """Multi-device scenarios modeled on a real 3-fan account (see issue #54
    comments from @odinb): devices disconnect independently, discovery is
    flaky (finds 2 of 3), and reconnect loops share the per-account
    discovery cache and client_lock.
    """

    def _make_entry_data(self, dk, *, connected=True):
        client = MagicMock() if connected else None
        return {
            "local_client": client,
            "local_generation": 1 if connected else 0,
            "local_codes": {"power"} if connected else set(),
            "properties": [
                {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL"},
            ],
            "temperature_prop": None,
            "auth_key": "dGVzdGtleQ==",
            "pk": "pk1",
            "dk": dk,
            "uid": "u1",
        }

    def _make_three_fan_hass(self, e1_data, e2_data, e3_data, local_devices):
        hass = make_hass()
        local_clients = {}
        for eid, edata in [("e1", e1_data), ("e2", e2_data), ("e3", e3_data)]:
            if edata["local_client"] is not None:
                local_clients[eid] = edata["local_client"]
        hass.data[DOMAIN] = {
            "e1": e1_data,
            "e2": e2_data,
            "e3": e3_data,
            "_accounts": {"u1": {
                "local_devices": local_devices,
                "local_clients": local_clients,
            }},
            "_client_locks": {"u1": asyncio.Lock()},
        }
        return hass

    def test_one_fan_disconnect_leaves_others_untouched(self):
        """Fan dk1 drops — dk2 and dk3 stay local, their local_clients and
        local_codes are not affected."""
        e1 = self._make_entry_data("dk1")
        e2 = self._make_entry_data("dk2")
        e3 = self._make_entry_data("dk3")
        hass = self._make_three_fan_hass(e1, e2, e3, {})

        handler = _make_local_disconnect_handler(hass, "e1", "u1", "pk1", "dk1", 1)
        handler()

        assert e1["local_client"] is None
        assert e1["local_codes"] == set()
        assert e2["local_client"] is not None
        assert e2["local_codes"] == {"power"}
        assert e3["local_client"] is not None
        assert e3["local_codes"] == {"power"}
        assert "e1" not in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]
        assert "e2" in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]
        assert "e3" in hass.data[DOMAIN]["_accounts"]["u1"]["local_clients"]

    @pytest.mark.asyncio
    async def test_two_fans_reconnect_share_single_discovery(self, mock_landbook_api):
        """dk1 and dk2 both disconnect and run reconnect loops. Both exhaust
        their cached-IP tries and fall back to discovery — the second loop
        should reuse the first's result via the shared cache, not broadcast
        again."""
        api = mock_landbook_api

        e1 = self._make_entry_data("dk1", connected=False)
        e2 = self._make_entry_data("dk2", connected=False)
        e3 = self._make_entry_data("dk3")

        fresh_dk1 = DiscoveredDevice(
            product_key="pk1", device_key="dk1", ip="10.0.0.11", port=6607, version=1
        )
        fresh_dk2 = DiscoveredDevice(
            product_key="pk1", device_key="dk2", ip="10.0.0.12", port=6607, version=1
        )
        api.discover_devices.return_value = [fresh_dk1, fresh_dk2]

        # No cached entries for dk1/dk2 — forces immediate discovery
        hass = self._make_three_fan_hass(e1, e2, e3, {})

        client_per_dk = {}

        def _make_client(pk, dk, auth, ip, port):
            c = MagicMock()
            client_per_dk[dk] = c
            return c

        api.local_client_cls.side_effect = _make_client

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            # Run both reconnect loops — they serialize on client_lock
            await _async_local_reconnect_loop(
                hass, "e1", "u1", "pk1", "dk1", "auth1"
            )
            await _async_local_reconnect_loop(
                hass, "e2", "u1", "pk1", "dk2", "auth2"
            )
        finally:
            asyncio.sleep = original_sleep

        assert e1["local_client"] is client_per_dk["dk1"]
        assert e2["local_client"] is client_per_dk["dk2"]
        # Discovery ran once for the first loop; the second reused the
        # cache that the first populated.
        api.discover_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_finds_two_of_three_fans(self, mock_landbook_api):
        """Real-world flakiness: discovery only finds dk1 and dk3 — dk2
        keeps retrying (with backoff) instead of giving up or crashing.
        Meanwhile dk1 and dk3 reconnect successfully."""
        api = mock_landbook_api

        e1 = self._make_entry_data("dk1", connected=False)
        e2 = self._make_entry_data("dk2", connected=False)
        e3 = self._make_entry_data("dk3", connected=False)

        # Discovery only finds dk1 and dk3
        fresh_dk1 = DiscoveredDevice(
            product_key="pk1", device_key="dk1", ip="10.0.0.11", port=6607, version=1
        )
        fresh_dk3 = DiscoveredDevice(
            product_key="pk1", device_key="dk3", ip="10.0.0.13", port=6607, version=1
        )
        api.discover_devices.return_value = [fresh_dk1, fresh_dk3]

        # No cached IPs at all
        hass = self._make_three_fan_hass(e1, e2, e3, {})

        clients = {}

        def _make_client(pk, dk, auth, ip, port):
            c = MagicMock()
            clients[dk] = c
            return c

        api.local_client_cls.side_effect = _make_client

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(
                hass, "e1", "u1", "pk1", "dk1", "auth1"
            )
            await _async_local_reconnect_loop(
                hass, "e3", "u1", "pk1", "dk3", "auth3"
            )
        finally:
            asyncio.sleep = original_sleep

        assert e1["local_client"] is clients["dk1"]
        assert e3["local_client"] is clients["dk3"]

        # dk2's loop: discovery doesn't find it, so it stays disconnected
        # and the loop keeps retrying. Simulate 2 iterations to prove it
        # doesn't crash and does back off.
        iteration = {"n": 0}

        async def _counting_sleep(delay):
            iteration["n"] += 1
            if iteration["n"] >= 2:
                # After 2 retries, remove entry_data to stop the loop
                hass.data[DOMAIN].pop("e2", None)

        asyncio.sleep = AsyncMock(side_effect=_counting_sleep)
        try:
            await _async_local_reconnect_loop(
                hass, "e2", "u1", "pk1", "dk2", "auth2"
            )
        finally:
            asyncio.sleep = original_sleep

        assert "dk2" not in clients
        assert iteration["n"] >= 2

    @pytest.mark.asyncio
    async def test_one_fan_reconnect_updates_shared_cache_for_others(self, mock_landbook_api):
        """dk1's reconnect runs fresh discovery which finds all 3 devices
        with new IPs. When dk3 later disconnects and reconnects, it should
        use the updated cached IP from dk1's discovery, not re-discover."""
        api = mock_landbook_api

        e1 = self._make_entry_data("dk1", connected=False)
        e2 = self._make_entry_data("dk2")
        e3 = self._make_entry_data("dk3")

        # Stale cached IPs
        stale = {
            ("pk1", "dk1"): DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.1", port=6607, version=1
            ),
            ("pk1", "dk2"): DiscoveredDevice(
                product_key="pk1", device_key="dk2", ip="10.0.0.2", port=6607, version=1
            ),
            ("pk1", "dk3"): DiscoveredDevice(
                product_key="pk1", device_key="dk3", ip="10.0.0.3", port=6607, version=1
            ),
        }
        hass = self._make_three_fan_hass(e1, e2, e3, stale)

        # dk1's cached IP fails 3 times, triggering fresh discovery
        attempt = {"count": 0}

        def _connect_side_effect(timeout):
            attempt["count"] += 1
            if attempt["count"] <= 3:
                raise ConnectionError("refused")

        new_client = MagicMock()
        new_client.connect = MagicMock(side_effect=_connect_side_effect)
        api.local_client_cls.return_value = new_client

        # Fresh discovery returns all 3 with new IPs
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.51", port=6607, version=1
            ),
            DiscoveredDevice(
                product_key="pk1", device_key="dk2", ip="10.0.0.52", port=6607, version=1
            ),
            DiscoveredDevice(
                product_key="pk1", device_key="dk3", ip="10.0.0.53", port=6607, version=1
            ),
        ]

        original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(
                hass, "e1", "u1", "pk1", "dk1", "auth1"
            )
        finally:
            asyncio.sleep = original_sleep

        # dk1 reconnected on the new IP
        assert e1["local_client"] is new_client

        # The shared cache now has the new IPs for all 3 devices
        acct = hass.data[DOMAIN]["_accounts"]["u1"]
        assert acct["local_devices"][("pk1", "dk3")].ip == "10.0.0.53"

        # Now dk3 disconnects — its reconnect should use the updated
        # cached IP (10.0.0.53), not trigger a new discovery
        e3["local_client"] = None
        e3["local_generation"] = 1
        e3["local_codes"] = set()

        dk3_client = MagicMock()
        api.local_client_cls.return_value = dk3_client
        api.discover_devices.reset_mock()

        asyncio.sleep = AsyncMock()
        try:
            await _async_local_reconnect_loop(
                hass, "e3", "u1", "pk1", "dk3", "auth3"
            )
        finally:
            asyncio.sleep = original_sleep

        assert e3["local_client"] is dk3_client
        # Used the cached IP from dk1's discovery, no new broadcast
        create_calls = [c for c in api.local_client_cls.call_args_list if c.args[1] == "dk3"]
        assert create_calls[-1].args[3] == "10.0.0.53"
        api.discover_devices.assert_not_called()
