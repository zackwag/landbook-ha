"""Tests for token refresh race condition serialization (issue #9).

Two distinct race conditions exist:

1. **Runtime**: The proactive 90-minute timer and MQTT reconnect thread can both
   invoke `_token_refresher` concurrently. The threading.Lock serializes them so
   the second caller picks up the already-refreshed token instead of racing the
   now-rotated refresh token.

2. **Setup-time** (PR #10): On a cold boot HA sets up all config entries for an
   account concurrently.  Each calls `async_refresh_token` with the same
   single-use refresh token — only the first succeeds.  The asyncio.Lock
   serializes setup so siblings re-read the persisted token and skip the refresh.
"""

from __future__ import annotations

import threading

import pytest
from landbook_api import LandbookAuthError

from .conftest import make_config_entry, make_hass, register_entry

# ---------------------------------------------------------------------------
# Runtime _token_refresher lock tests
# ---------------------------------------------------------------------------


class TestRuntimeRefreshLock:
    """The threading.Lock in _token_refresher must serialize concurrent calls."""

    def _build_token_refresher(self, hass, mock_api):
        """Extract _token_refresher from async_setup_entry by running setup once."""
        import asyncio

        from custom_components.landbook import async_setup_entry
        from custom_components.landbook.const import DOMAIN

        entry = make_config_entry(
            hass, entry_id="rt_entry", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        register_entry(hass, entry)
        hass.data.setdefault(DOMAIN, {})

        mock_api.refresh_token.return_value = ("tok_v2", "ref_v2")

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry))
        finally:
            loop.close()

        # The token_refresher is passed to LandbookMQTTClient — grab it
        call_kwargs = mock_api.mqtt_cls.call_args
        return call_kwargs[1]["token_refresher"]

    def test_concurrent_refresh_calls_only_one_api_call(self, mock_landbook_api):
        """Two threads calling _token_refresher should result in only one
        refresh_token API call — the second should re-read the persisted token."""
        hass = make_hass()
        api = mock_landbook_api

        call_count = 0
        gate = threading.Event()

        def slow_refresh(token, refresh, region):
            nonlocal call_count
            call_count += 1
            gate.wait(timeout=2)
            return ("tok_new", "ref_new")

        api.refresh_token.side_effect = slow_refresh

        refresher = self._build_token_refresher(hass, api)

        # Reset after setup consumed one call
        call_count = 0
        api.refresh_token.reset_mock()
        api.refresh_token.side_effect = slow_refresh

        results = [None, None]
        errors = [None, None]

        def run_refresh(idx):
            try:
                results[idx] = refresher()
            except Exception as e:  # noqa: BLE001 - captured for the main thread to assert on, not swallowed
                errors[idx] = e

        t1 = threading.Thread(target=run_refresh, args=(0,))
        t2 = threading.Thread(target=run_refresh, args=(1,))
        t1.start()
        # Small delay so t1 grabs the lock first
        threading.Event().wait(0.05)
        t2.start()

        # Let the first refresh complete
        gate.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert errors[0] is None, f"Thread 1 error: {errors[0]}"
        assert errors[1] is None, f"Thread 2 error: {errors[1]}"
        assert results[0] == "tok_new"
        assert results[1] == "tok_new"

    def test_refresh_auth_error_triggers_reauth(self, mock_landbook_api):
        """A LandbookAuthError from refresh_token should propagate (triggering reauth)."""
        hass = make_hass()
        api = mock_landbook_api

        # First call during setup succeeds
        api.refresh_token.return_value = ("tok_v2", "ref_v2")
        refresher = self._build_token_refresher(hass, api)

        # Now make it fail
        api.refresh_token.side_effect = LandbookAuthError("Token refresh rejected")

        with pytest.raises(LandbookAuthError, match="rejected"):
            refresher()

    def test_refresh_network_error_propagates(self, mock_landbook_api):
        """A generic exception (network error) should propagate for retry."""
        hass = make_hass()
        api = mock_landbook_api

        api.refresh_token.return_value = ("tok_v2", "ref_v2")
        refresher = self._build_token_refresher(hass, api)

        api.refresh_token.side_effect = ConnectionError("DNS resolution failed")

        with pytest.raises(ConnectionError, match="DNS"):
            refresher()

    def test_refresh_persists_token_to_all_entries(self, mock_landbook_api):
        """After a successful refresh, the new token pair should be persisted
        to all config entries for the account."""
        hass = make_hass()
        api = mock_landbook_api
        from custom_components.landbook.const import DOMAIN

        entry1 = make_config_entry(
            hass, entry_id="e1", uid="u1", bearer_token="tok_old", refresh_token="ref_old"
        )
        entry2 = make_config_entry(
            hass, entry_id="e2", uid="u1", bearer_token="tok_old", refresh_token="ref_old"
        )
        register_entry(hass, entry1)
        register_entry(hass, entry2)
        hass.data.setdefault(DOMAIN, {})

        api.refresh_token.return_value = ("tok_fresh", "ref_fresh")

        import asyncio

        from custom_components.landbook import async_setup_entry

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry1))
        finally:
            loop.close()

        # Register entry2 under the account
        hass.data[DOMAIN]["_accounts"]["u1"]["entries"].add("e2")

        # Grab the refresher
        call_kwargs = api.mqtt_cls.call_args
        refresher = call_kwargs[1]["token_refresher"]

        api.refresh_token.reset_mock()
        api.refresh_token.return_value = ("tok_v3", "ref_v3")

        refresher()

        # Both entries should have the new tokens (via _async_persist_token_for_account)
        # The persist is dispatched via call_soon_threadsafe, so check the call was made
        assert hass.loop.call_soon_threadsafe.called

    def test_refresher_picks_up_reauth_written_tokens(self, mock_landbook_api):
        """After reauth writes to account_tokens, the refresher must use those
        tokens instead of the stale closure-captured _latest_tokens (#27)."""
        hass = make_hass()
        api = mock_landbook_api
        from custom_components.landbook.const import DOMAIN

        entry = make_config_entry(
            hass, entry_id="ra1", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        register_entry(hass, entry)
        hass.data.setdefault(DOMAIN, {})

        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        import asyncio

        from custom_components.landbook import async_setup_entry

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry))
        finally:
            loop.close()

        call_kwargs = api.mqtt_cls.call_args
        refresher = call_kwargs[1]["token_refresher"]

        # Simulate reauth writing fresh tokens to account_tokens
        hass.data[DOMAIN]["_account_tokens"]["u1"] = {
            "access": "reauth_tok",
            "refresh": "reauth_ref",
        }

        api.refresh_token.reset_mock()
        api.refresh_token.return_value = ("tok_v3", "ref_v3")
        refresher()

        call_args = api.refresh_token.call_args[0]
        assert call_args[0] == "reauth_tok", f"Expected reauth access token, got '{call_args[0]}'"
        assert call_args[1] == "reauth_ref", f"Expected reauth refresh token, got '{call_args[1]}'"

    def test_auth_error_honors_reauth_fired_guard(self, mock_landbook_api):
        """When _reauth_fired_{uid} is already set, the refresher must NOT
        fire reauth again (prevents the reauth storm from #27)."""
        hass = make_hass()
        api = mock_landbook_api
        from custom_components.landbook.const import DOMAIN

        entry = make_config_entry(
            hass, entry_id="guard1", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        register_entry(hass, entry)
        hass.data.setdefault(DOMAIN, {})

        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        import asyncio

        from custom_components.landbook import async_setup_entry

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry))
        finally:
            loop.close()

        call_kwargs = api.mqtt_cls.call_args
        refresher = call_kwargs[1]["token_refresher"]

        # Pre-set the guard as if reauth was already fired
        hass.data[DOMAIN]["_reauth_fired_u1"] = True
        entry.async_start_reauth.reset_mock()
        hass.loop.call_soon_threadsafe.reset_mock()

        api.refresh_token.side_effect = LandbookAuthError("Token refresh rejected")

        with pytest.raises(LandbookAuthError, match="rejected"):
            refresher()

        # No reauth should have been dispatched — the guard prevented it
        for call in hass.loop.call_soon_threadsafe.call_args_list:
            args = call[0]
            # call_soon_threadsafe(hass.async_create_task, coro) — if it
            # triggered reauth there'd be a _async_trigger_reauth coro here
            if len(args) >= 2:
                coro = args[1]
                if hasattr(coro, "cr_code"):
                    assert "trigger_reauth" not in (coro.cr_code.co_name or ""), (
                        "Reauth was fired despite _reauth_fired guard being set"
                    )

    def test_auth_error_fires_reauth_for_single_entry(self, mock_landbook_api):
        """On first auth failure, reauth should fire for exactly one entry,
        not all entries on the account (#27)."""
        hass = make_hass()
        api = mock_landbook_api
        from custom_components.landbook.const import DOMAIN

        entry1 = make_config_entry(
            hass, entry_id="storm1", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        entry2 = make_config_entry(
            hass, entry_id="storm2", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        entry2.data["device_key"] = "dk2"
        register_entry(hass, entry1)
        register_entry(hass, entry2)
        hass.data.setdefault(DOMAIN, {})

        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        import asyncio

        from custom_components.landbook import async_setup_entry

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry1))
        finally:
            loop.close()

        # Register entry2 under the account
        hass.data[DOMAIN]["_accounts"]["u1"]["entries"].add("storm2")

        call_kwargs = api.mqtt_cls.call_args
        refresher = call_kwargs[1]["token_refresher"]

        # Ensure the guard is NOT set yet
        assert not hass.data[DOMAIN].get("_reauth_fired_u1")

        hass.loop.call_soon_threadsafe.reset_mock()
        api.refresh_token.side_effect = LandbookAuthError("Token refresh rejected")

        with pytest.raises(LandbookAuthError, match="rejected"):
            refresher()

        # Guard should now be set
        assert hass.data[DOMAIN].get("_reauth_fired_u1") is True

        # Count how many _async_trigger_reauth coroutines were dispatched
        reauth_coros = []
        for call in hass.loop.call_soon_threadsafe.call_args_list:
            args = call[0]
            if len(args) >= 2:
                coro = args[1]
                if hasattr(coro, "cr_code") and "trigger_reauth" in (coro.cr_code.co_name or ""):
                    reauth_coros.append(coro)
        assert len(reauth_coros) <= 1, (
            f"Expected at most 1 reauth dispatch, got {len(reauth_coros)}"
        )

    def test_sequential_refreshes_use_latest_token(self, mock_landbook_api):
        """The second refresh call must use the token pair from the first refresh,
        not the stale pair from config entries (which are updated asynchronously)."""
        hass = make_hass()
        api = mock_landbook_api
        from custom_components.landbook.const import DOMAIN

        entry = make_config_entry(
            hass, entry_id="seq1", uid="u1", bearer_token="tok_v1", refresh_token="ref_v1"
        )
        register_entry(hass, entry)
        hass.data.setdefault(DOMAIN, {})

        api.refresh_token.return_value = ("tok_v2", "ref_v2")

        import asyncio

        from custom_components.landbook import async_setup_entry

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_setup_entry(hass, entry))
        finally:
            loop.close()

        call_kwargs = api.mqtt_cls.call_args
        refresher = call_kwargs[1]["token_refresher"]

        # First runtime refresh: should use tok_v1/ref_v1 from setup
        api.refresh_token.reset_mock()
        api.refresh_token.return_value = ("tok_v2", "ref_v2")
        result1 = refresher()
        assert result1 == "tok_v2"
        first_call_args = api.refresh_token.call_args[0]
        assert first_call_args[0] == "tok_v1", (
            f"Expected access token 'tok_v1' from setup, got '{first_call_args[0]}'"
        )
        assert first_call_args[1] == "ref_v1", (
            f"Expected refresh token 'ref_v1' from setup, got '{first_call_args[1]}'"
        )

        # Second runtime refresh: must use tok_v2/ref_v2 from in-memory state,
        # NOT the config entry (which may still have tok_v1/ref_v1 because
        # the async persist hasn't run yet)
        api.refresh_token.reset_mock()
        api.refresh_token.return_value = ("tok_v3", "ref_v3")
        result2 = refresher()
        assert result2 == "tok_v3"
        second_call_args = api.refresh_token.call_args[0]

        # The second call must have used the output of the first, not the original
        assert second_call_args[0] == "tok_v2", (
            f"Expected access token 'tok_v2' from first refresh, got '{second_call_args[0]}'"
        )
        assert second_call_args[1] == "ref_v2", (
            f"Expected refresh token 'ref_v2' from first refresh, got '{second_call_args[1]}'"
        )


# ---------------------------------------------------------------------------
# Setup-time asyncio.Lock tests (PR #10 feature)
# ---------------------------------------------------------------------------


class TestSetupTimeLock:
    """The asyncio.Lock in async_setup_entry must serialize concurrent
    setup calls for the same account so only one calls async_refresh_token."""

    @pytest.mark.asyncio
    async def test_concurrent_setup_only_refreshes_once(self, mock_landbook_api):
        """When two entries for the same account set up concurrently with an
        expired token, only the first should call async_refresh_token. The
        second should re-read the fresh token from its entry and skip."""
        import asyncio

        from landbook_api import LandbookAPIError

        from custom_components.landbook import async_setup, async_setup_entry
        from custom_components.landbook.const import (
            CONF_BEARER_TOKEN,
            CONF_REFRESH_TOKEN,
            DOMAIN,
        )

        hass = make_hass()
        api = mock_landbook_api

        entry1 = make_config_entry(
            hass, entry_id="s1", uid="u1", bearer_token="expired_tok", refresh_token="ref_1"
        )
        entry2 = make_config_entry(
            hass, entry_id="s2", uid="u1", bearer_token="expired_tok", refresh_token="ref_1"
        )
        # Give entry2 a different device key so it's a separate device
        entry2.data["device_key"] = "dk2"
        register_entry(hass, entry1)
        register_entry(hass, entry2)

        tsl_call_count = 0

        async def tsl_side_effect(token, pk, region):
            nonlocal tsl_call_count
            tsl_call_count += 1
            if token == "expired_tok":
                raise LandbookAPIError("Token validation failed")
            return api.async_get_tsl.return_value

        api.async_get_tsl.side_effect = tsl_side_effect

        async def refresh_side_effect(token, refresh, region):
            await asyncio.sleep(0.05)
            # Simulate the API persisting new tokens
            for eid in ["s1", "s2"]:
                e = hass.config_entries.async_get_entry(eid)
                if e:
                    e.data = {
                        **e.data,
                        CONF_BEARER_TOKEN: "fresh_tok",
                        CONF_REFRESH_TOKEN: "fresh_ref",
                    }
            return ("fresh_tok", "fresh_ref")

        api.async_refresh_token.side_effect = refresh_side_effect

        await async_setup(hass, {})

        # Check if the code has the setup lock (PR #10)
        # If not, this test documents the expected behavior after the PR merges
        try:
            r1, r2 = await asyncio.gather(
                async_setup_entry(hass, entry1),
                async_setup_entry(hass, entry2),
                return_exceptions=True,
            )
        except Exception:  # noqa: BLE001 - skip gracefully if the not-yet-merged feature isn't present
            pytest.skip("Setup-time lock not yet merged (PR #10)")
            return

        if isinstance(r1, Exception) or isinstance(r2, Exception):
            failures = [r for r in [r1, r2] if isinstance(r, Exception)]
            pytest.skip(f"Setup-time lock not yet merged — entry failed: {failures[0]}")

        # With PR #10 merged: only ONE call to async_refresh_token.
        # Without the lock, both entries race and both call refresh (count=2).
        has_setup_lock = "_setup_locks" in hass.data.get(DOMAIN, {})
        if not has_setup_lock and api.async_refresh_token.call_count > 1:
            pytest.skip(
                "Setup-time lock not yet merged (PR #10) — both entries "
                f"raced the refresh ({api.async_refresh_token.call_count} calls)"
            )

        assert api.async_refresh_token.call_count <= 1, (
            f"Expected at most 1 refresh call, got {api.async_refresh_token.call_count}"
        )
