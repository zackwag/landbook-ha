"""Tests for TSL model caching (CONF_TSL_CACHE) in async_setup_entry."""

from __future__ import annotations

import pytest

from custom_components.landbook import async_setup, async_setup_entry
from custom_components.landbook.const import CONF_TSL_CACHE, DOMAIN

from .conftest import make_config_entry, make_hass, register_entry


class TestTslCache:
    @pytest.mark.asyncio
    async def test_first_setup_fetches_and_caches_tsl(self, mock_landbook_api):
        hass = make_hass()
        api = mock_landbook_api

        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        api.async_get_tsl.assert_called_once()
        assert entry.data[CONF_TSL_CACHE] == api.async_get_tsl.return_value

    @pytest.mark.asyncio
    async def test_cached_tsl_skips_fetch_on_next_setup(self, mock_landbook_api):
        hass = make_hass()
        api = mock_landbook_api

        cached = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []}
        ]
        entry = make_config_entry(hass, entry_id="e1", uid="u1")
        entry.data[CONF_TSL_CACHE] = cached
        register_entry(hass, entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, entry)

        api.async_get_tsl.assert_not_called()
        assert hass.data[DOMAIN]["e1"]["properties"] == cached

    @pytest.mark.asyncio
    async def test_second_entry_on_same_account_caches_independently(self, mock_landbook_api):
        """Each entry caches its own TSL — a sibling with cached TSL must
        not skip the fetch for one that doesn't have it yet."""
        hass = make_hass()
        api = mock_landbook_api

        cached_entry = make_config_entry(hass, entry_id="e1", uid="u1")
        cached_entry.data[CONF_TSL_CACHE] = [
            {"code": "power", "id": 1, "name": "Power", "dataType": "BOOL", "sort": 0, "specs": []}
        ]
        register_entry(hass, cached_entry)

        fresh_entry = make_config_entry(hass, entry_id="e2", uid="u1")
        register_entry(hass, fresh_entry)

        await async_setup(hass, {})
        await async_setup_entry(hass, cached_entry)
        await async_setup_entry(hass, fresh_entry)

        api.async_get_tsl.assert_called_once()  # only for the entry without a cache
        assert CONF_TSL_CACHE in fresh_entry.data
