"""Tests for config flow and options flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.landbook.config_flow import LandbookFanConfigFlow, LandbookOptionsFlow
from custom_components.landbook.const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_KEY,
    CONF_PRODUCT_NAME,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SIGNAL_STRENGTH,
    CONF_TEMP_UNIT,
    CONF_UID,
    DOMAIN,
    TEMP_UNIT_C,
    TEMP_UNIT_F,
)


MOCK_DEVICES = [
    {
        "deviceKey": "dk1",
        "productKey": "pk1",
        "deviceName": "Living Room Fan",
        "productName": "OmniBreeze",
    },
    {
        "deviceKey": "dk2",
        "productKey": "pk2",
        "deviceName": "Bedroom Fan",
        "productName": "OmniBreeze",
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
    @pytest.mark.asyncio
    async def test_pick_device_creates_entry(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()
        flow._email = "a@b.com"
        flow._bearer_token = "tok"
        flow._refresh_token = "ref"
        flow._uid = "uid1"
        flow._region = "us"
        flow._devices = MOCK_DEVICES

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_pick_device({"device": "Living Room Fan"})

        assert result["type"] == "create_entry"
        assert result["title"] == "Living Room Fan"
        assert result["data"][CONF_DEVICE_KEY] == "dk1"
        assert result["data"][CONF_PRODUCT_KEY] == "pk1"
        assert result["data"][CONF_BEARER_TOKEN] == "tok"
        assert result["data"][CONF_REFRESH_TOKEN] == "ref"

    @pytest.mark.asyncio
    async def test_pick_device_not_found_shows_error(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()
        flow._devices = MOCK_DEVICES

        result = await flow.async_step_pick_device({"device": "Nonexistent Fan"})

        assert result["type"] == "form"
        assert result["errors"]["base"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_pick_device_fetch_failure_shows_error(self):
        flow = LandbookFanConfigFlow()
        flow.hass = MagicMock()
        flow._bearer_token = "tok"
        flow._region = "us"
        flow._devices = []

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


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    def _make_flow(self, entry):
        flow = LandbookOptionsFlow()
        with patch.object(
            type(flow), "config_entry",
            new_callable=PropertyMock, return_value=entry, create=True,
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
        entry.options = {}
        entry.data = {}

        for flow in self._make_flow(entry):
            result = await flow.async_step_init(
                {CONF_TEMP_UNIT: TEMP_UNIT_C, CONF_SIGNAL_STRENGTH: True}
            )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_TEMP_UNIT] == TEMP_UNIT_C
        assert result["data"][CONF_SIGNAL_STRENGTH] is True
