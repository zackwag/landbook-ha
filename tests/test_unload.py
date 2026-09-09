"""Tests for async_unload_entry lifecycle."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

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
