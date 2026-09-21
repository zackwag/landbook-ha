"""Tests for config flow and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.landbook.config_flow import LandbookFanConfigFlow, LandbookOptionsFlow
from custom_components.landbook.const import (
    CONF_AUTH_KEY,
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_KEY,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SIGNAL_STRENGTH,
    CONF_TEMP_UNIT,
    CONF_UID,
    TEMP_UNIT_C,
)

MOCK_DEVICES = [
    {
        "deviceKey": "dk1",
        "productKey": "pk1",
        "deviceName": "Living Room Fan",
        "productName": "OmniBreeze",
        "authKey": "dGVzdGtleQ==",
    },
    {
        "deviceKey": "dk2",
        "productKey": "pk2",
        "deviceName": "Bedroom Fan",
        "productName": "OmniBreeze",
        # Deliberately no authKey — real accounts shouldn't hit this, but
        # the flow must not crash if the device list ever omits it.
    },
]


# ---------------------------------------------------------------------------
# Login step
# ---------------------------------------------------------------------------


class TestUserStep:
    @pytest.mark.asyncio
    async def test_login_success_advances_to_pick_device(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        with (
            patch(
                "custom_components.landbook.config_flow.async_login",
                new_callable=AsyncMock,
                return_value=("tok", "uid1", "ref"),
            ),
            patch(
                "custom_components.landbook.config_flow.async_get_device_list",
                new_callable=AsyncMock,
                return_value=MOCK_DEVICES,
            ),
        ):
            result = await flow.async_step_user(
                {CONF_EMAIL: "a@b.com", CONF_PASSWORD: "pw", CONF_REGION: "us"}
            )

        assert result["type"] == "form"
        assert result["step_id"] == "pick_device"

    @pytest.mark.asyncio
    async def test_login_auth_error_shows_form_with_error(self):
        from landbook_api import LandbookAuthError

        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.landbook.config_flow.async_login",
            new_callable=AsyncMock,
            side_effect=LandbookAuthError("bad creds"),
        ):
            result = await flow.async_step_user(
                {CONF_EMAIL: "a@b.com", CONF_PASSWORD: "pw", CONF_REGION: "us"}
            )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_login_generic_error_shows_cannot_connect(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        with patch(
            "custom_components.landbook.config_flow.async_login",
            new_callable=AsyncMock,
            side_effect=ConnectionError("timeout"),
        ):
            result = await flow.async_step_user(
                {CONF_EMAIL: "a@b.com", CONF_PASSWORD: "pw", CONF_REGION: "us"}
            )

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_no_input_shows_form(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"


# ---------------------------------------------------------------------------
# Device picker step
# ---------------------------------------------------------------------------


class TestPickDeviceStep:
    def _make_flow(self, hass_entries=(), **overrides):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=list(hass_entries))
        flow._email = overrides.get("email", "a@b.com")
        flow._bearer_token = overrides.get("bearer_token", "tok")
        flow._refresh_token = overrides.get("refresh_token", "ref")
        flow._uid = overrides.get("uid", "uid1")
        flow._region = overrides.get("region", "us")
        flow._devices = overrides.get("devices", MOCK_DEVICES)
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        return flow

    @pytest.mark.asyncio
    async def test_pick_device_creates_entry(self):
        flow = self._make_flow()

        result = await flow.async_step_pick_device({"device": "Living Room Fan"})

        assert result["type"] == "create_entry"
        assert result["title"] == "Living Room Fan"
        assert result["data"][CONF_DEVICE_KEY] == "dk1"
        assert result["data"][CONF_PRODUCT_KEY] == "pk1"
        assert result["data"][CONF_BEARER_TOKEN] == "tok"
        assert result["data"][CONF_REFRESH_TOKEN] == "ref"
        assert result["data"][CONF_AUTH_KEY] == "dGVzdGtleQ=="

    @pytest.mark.asyncio
    async def test_pick_device_missing_auth_key_defaults_empty(self):
        flow = self._make_flow()

        result = await flow.async_step_pick_device({"device": "Bedroom Fan"})

        assert result["data"][CONF_AUTH_KEY] == ""

    @pytest.mark.asyncio
    async def test_pick_device_not_found_shows_error(self):
        flow = self._make_flow(hass_entries=[])

        result = await flow.async_step_pick_device({"device": "Nonexistent Fan"})

        assert result["type"] == "form"
        assert result["errors"]["base"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_pick_device_fetch_failure_shows_error(self):
        flow = self._make_flow(hass_entries=[], devices=[])

        with patch(
            "custom_components.landbook.config_flow.async_get_device_list",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network error"),
        ):
            result = await flow.async_step_pick_device(None)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Reauth flow
# ---------------------------------------------------------------------------


class TestReauthFlow:
    @pytest.mark.asyncio
    async def test_reauth_success_aborts(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        reauth_entry = MagicMock()
        reauth_entry.data = {
            CONF_EMAIL: "a@b.com",
            CONF_REGION: "us",
            CONF_UID: "uid1",
        }
        reauth_entry.entry_id = "e1"
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
        flow.hass.config_entries.async_entries = MagicMock(return_value=[reauth_entry])
        flow.hass.config_entries.async_update_entry = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()

        with patch(
            "custom_components.landbook.config_flow.async_login",
            new_callable=AsyncMock,
            return_value=("new_tok", "uid1", "new_ref"),
        ):
            result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "new_pw"})

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"

    @pytest.mark.asyncio
    async def test_reauth_bad_password_shows_error(self):
        from landbook_api import LandbookAuthError

        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        reauth_entry = MagicMock()
        reauth_entry.data = {CONF_EMAIL: "a@b.com", CONF_REGION: "us"}
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)

        with patch(
            "custom_components.landbook.config_flow.async_login",
            new_callable=AsyncMock,
            side_effect=LandbookAuthError("wrong"),
        ):
            result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "bad"})

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_reauth_no_input_shows_form(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        reauth_entry = MagicMock()
        reauth_entry.data = {CONF_EMAIL: "a@b.com", CONF_REGION: "us"}
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)

        result = await flow.async_step_reauth_confirm(None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

    @pytest.mark.asyncio
    async def test_reauth_updates_in_memory_tokens_and_clears_halt(self):
        """After reauth, account_tokens must hold the fresh pair, the
        _reauth_fired guard must be cleared, and the MQTT client must be
        un-halted with the new token (#27)."""
        from custom_components.landbook.const import DOMAIN

        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()

        mqtt_client = MagicMock()
        mqtt_client._reauth_pending = True

        flow.hass.data = {
            DOMAIN: {
                "_account_tokens": {},
                "_accounts": {"uid1": {"client": mqtt_client}},
                "_reauth_fired_uid1": True,
            }
        }

        reauth_entry = MagicMock()
        reauth_entry.data = {
            CONF_EMAIL: "a@b.com",
            CONF_REGION: "us",
            CONF_UID: "uid1",
        }
        reauth_entry.entry_id = "e1"
        flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
        flow.hass.config_entries.async_entries = MagicMock(return_value=[reauth_entry])
        flow.hass.config_entries.async_update_entry = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()

        with patch(
            "custom_components.landbook.config_flow.async_login",
            new_callable=AsyncMock,
            return_value=("new_tok", "uid1", "new_ref"),
        ):
            result = await flow.async_step_reauth_confirm({CONF_PASSWORD: "pw"})

        assert result["type"] == "abort"

        tokens = flow.hass.data[DOMAIN]["_account_tokens"]["uid1"]
        assert tokens == {"access": "new_tok", "refresh": "new_ref"}

        assert "_reauth_fired_uid1" not in flow.hass.data[DOMAIN]

        assert mqtt_client._reauth_pending is False
        mqtt_client.update_token.assert_called_once_with("new_tok")


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    def _make_flow(self, entry, hass=None):
        flow = LandbookOptionsFlow()
        if hass is None:
            hass = MagicMock()
            hass.config_entries.async_entries = MagicMock(return_value=[])
        flow.hass = hass
        with patch.object(
            type(flow),
            "config_entry",
            new_callable=PropertyMock,
            return_value=entry,
            create=True,
        ):
            yield flow

    @pytest.mark.asyncio
    async def test_options_init_returns_form(self):
        entry = MagicMock()
        entry.options = {}
        entry.data = {}

        for flow in self._make_flow(entry):
            result = await flow.async_step_init(None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_submit_creates_entry(self):
        entry = MagicMock()
        entry.entry_id = "e1"
        entry.options = {}
        entry.data = {}

        for flow in self._make_flow(entry):
            result = await flow.async_step_init(
                {
                    CONF_TEMP_UNIT: TEMP_UNIT_C,
                    CONF_SIGNAL_STRENGTH: True,
                }
            )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_TEMP_UNIT] == TEMP_UNIT_C
        assert result["data"][CONF_SIGNAL_STRENGTH] is True
