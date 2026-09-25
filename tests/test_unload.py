"""Tests for async_unload_entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.landbook.const import DOMAIN

from .conftest import make_config_entry, make_hass, register_entry


class TestUnloadEntry:
    @pytest.mark.asyncio
    async def test_unload_last_entry_disconnects_mqtt(self, mock_landbook_api):
        """Unloading the last entry for an account should disconnect MQTT."""
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        api = mock_landbook_api
        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        mqtt_client = hass.data[DOMAIN]["_accounts"]["u1"]["client"]

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        result = await async_unload_entry(hass, entry)

        assert result is True
        mqtt_client.disconnect.assert_called_once()
        assert "u1" not in hass.data[DOMAIN].get("_accounts", {})

    @pytest.mark.asyncio
    async def test_unload_non_last_entry_keeps_mqtt(self, mock_landbook_api):
        """Unloading one of two entries should keep the MQTT connection alive."""
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        api = mock_landbook_api
        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        entry1 = make_config_entry(hass, entry_id="e1", uid="u1")
        entry2 = make_config_entry(hass, entry_id="e2", uid="u1")
        entry2.data["device_key"] = "dk2"
        register_entry(hass, entry1)
        register_entry(hass, entry2)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry1)
        await async_setup_entry(hass, entry2)

        mqtt_client = hass.data[DOMAIN]["_accounts"]["u1"]["client"]

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        result = await async_unload_entry(hass, entry1)

        assert result is True
        mqtt_client.disconnect.assert_not_called()
        assert "u1" in hass.data[DOMAIN]["_accounts"]
        assert "e2" in hass.data[DOMAIN]["_accounts"]["u1"]["entries"]

    @pytest.mark.asyncio
    async def test_unload_race_account_deleted_during_disconnect(self, mock_landbook_api):
        """Unload must not KeyError if another coroutine deletes the account mid-teardown.

        Simulates the race: while one coroutine is awaiting client.disconnect,
        another coroutine removes accounts[uid].  When the first resumes it
        must not crash on accounts[uid].
        """
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        api = mock_landbook_api
        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        accounts = hass.data[DOMAIN]["_accounts"]

        async def _executor_that_deletes_account(fn, *args):
            """Run disconnect, then delete the account key to mimic a racing coroutine."""
            fn(*args)
            accounts.pop("u1", None)

        hass.async_add_executor_job = _executor_that_deletes_account

        result = await async_unload_entry(hass, entry)

        assert result is True
        assert "u1" not in accounts

    @pytest.mark.asyncio
    async def test_unload_failure_preserves_data(self, mock_landbook_api):
        """If platform unload fails, entry data should be preserved."""
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        api = mock_landbook_api
        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        result = await async_unload_entry(hass, entry)

        assert result is False
        assert "e1" in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_disconnects_local_client(self, mock_landbook_api):
        """A device with a live local-LAN connection should have it
        disconnected on unload, independent of the shared MQTT client
        (which stays up for any other entries on the account)."""
        from landbook_api.local_client import DiscoveredDevice

        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry
        from custom_components.landbook.const import CONF_AUTH_KEY

        hass = make_hass()
        api = mock_landbook_api
        api.discover_devices.return_value = [
            DiscoveredDevice(
                product_key="pk1", device_key="dk1", ip="10.0.0.5", port=6607, version=1
            )
        ]

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_AUTH_KEY] = "dGVzdGtleQ=="
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)
        assert hass.data[DOMAIN]["e1"]["local_client"] is api.local_client

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        result = await async_unload_entry(hass, entry)

        assert result is True
        api.local_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_unsubscribes_mqtt_callback(self, mock_landbook_api):
        """Each setup registers a per-device MQTT callback. Unload must
        remove it so a subsequent reload doesn't duplicate messages (#74)."""
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        api = mock_landbook_api
        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        mqtt_client = hass.data[DOMAIN]["_accounts"]["u1"]["client"]
        device_id = hass.data[DOMAIN]["e1"]["device_id"]

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        await async_unload_entry(hass, entry)

        mqtt_client.unsubscribe_device.assert_called_once()
        call_args = mqtt_client.unsubscribe_device.call_args
        assert call_args[0][0] == device_id
        assert callable(call_args[0][1])
