"""Tests for per-product platform gating."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.landbook.const import DEFAULT_PLATFORMS, DOMAIN, PRODUCT_PLATFORMS

from .conftest import make_config_entry, make_hass, register_entry


class TestPlatformGating:
    """async_setup_entry should forward only the platforms for the device's product key."""

    async def _setup(self, mock_landbook_api, hass, product_key):
        from custom_components.landbook import async_setup, async_setup_entry

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data["product_key"] = product_key
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)
        return entry

    @pytest.mark.asyncio
    async def test_omnibreeze_gets_all_platforms(self, mock_landbook_api):
        hass = make_hass()
        await self._setup(mock_landbook_api, hass, "p11vkW")

        forwarded = set(hass.config_entries.async_forward_entry_setups.call_args[0][1])
        assert forwarded == PRODUCT_PLATFORMS["p11vkW"]

    @pytest.mark.asyncio
    async def test_power_station_gets_sensor_only(self, mock_landbook_api):
        hass = make_hass()
        await self._setup(mock_landbook_api, hass, "p11tiQ")

        forwarded = set(hass.config_entries.async_forward_entry_setups.call_args[0][1])
        assert forwarded == {"sensor"}

    @pytest.mark.asyncio
    async def test_unknown_product_gets_default_platforms(self, mock_landbook_api):
        hass = make_hass()
        await self._setup(mock_landbook_api, hass, "pUnknown")

        forwarded = set(hass.config_entries.async_forward_entry_setups.call_args[0][1])
        assert forwarded == DEFAULT_PLATFORMS

    @pytest.mark.asyncio
    async def test_unload_uses_stored_platforms(self, mock_landbook_api):
        from custom_components.landbook import async_setup, async_setup_entry, async_unload_entry

        hass = make_hass()
        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data["product_key"] = "p11tiQ"
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        await async_unload_entry(hass, entry)

        unloaded = set(hass.config_entries.async_unload_platforms.call_args[0][1])
        assert unloaded == {"sensor"}
