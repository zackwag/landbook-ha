"""Config flow for Landbook integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import LandbookAuthError, async_get_device_list, async_login, async_refresh_token
from .const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_MUTE_ON_COMMAND,
    CONF_PASSWORD,
    CONF_PRODUCT_KEY,
    CONF_PRODUCT_NAME,
    CONF_REGION,
    CONF_UID,
    DEFAULT_REGION,
    DOMAIN,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)

REGION_OPTIONS = {key: cfg["label"] for key, cfg in REGIONS.items()}


class LandbookOptionsFlow(config_entries.OptionsFlow):
    """Allow changing options after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_MUTE_ON_COMMAND,
            self.config_entry.data.get(CONF_MUTE_ON_COMMAND, False),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_MUTE_ON_COMMAND, default=current): bool}
            ),
        )


class LandbookFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Landbook."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> LandbookOptionsFlow:
        return LandbookOptionsFlow()

    def __init__(self) -> None:
        self._email: str = ""
        self._bearer_token: str = ""
        self._uid: str = ""
        self._region: str = DEFAULT_REGION
        self._devices: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: choose region, collect email + password, attempt login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            region = user_input[CONF_REGION]
            try:
                bearer_token, uid = await async_login(email, password, region)
            except LandbookAuthError as exc:
                _LOGGER.error("Landbook login error: %s", exc)
                errors["base"] = "invalid_auth"
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Unexpected login error: %s", exc)
                errors["base"] = "cannot_connect"
            else:
                self._email = email
                self._bearer_token = bearer_token
                self._uid = uid
                self._region = region
                return await self.async_step_pick_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=DEFAULT_REGION): vol.In(REGION_OPTIONS),
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-authenticate when the stored token is no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                bearer_token, uid = await async_login(
                    reauth_entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    reauth_entry.data.get(CONF_REGION, DEFAULT_REGION),
                )
            except LandbookAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_BEARER_TOKEN: bearer_token, CONF_UID: uid},
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": reauth_entry.data.get(CONF_EMAIL, "")},
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: pick which device to add."""
        errors: dict[str, str] = {}

        if not self._devices:
            try:
                self._devices = await async_get_device_list(self._bearer_token, self._region)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Failed to fetch device list: %s", exc)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            selected_name = user_input["device"]
            device = next(
                (d for d in self._devices if d["deviceName"] == selected_name),
                None,
            )
            if device is None:
                errors["base"] = "device_not_found"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{device['deviceKey']}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device["deviceName"],
                    data={
                        CONF_REGION: self._region,
                        CONF_EMAIL: self._email,
                        CONF_BEARER_TOKEN: self._bearer_token,
                        CONF_UID: self._uid,
                        CONF_DEVICE_KEY: device["deviceKey"],
                        CONF_PRODUCT_KEY: device["productKey"],
                        CONF_DEVICE_NAME: device["deviceName"],
                        CONF_PRODUCT_NAME: device.get("productName", ""),
                        CONF_MUTE_ON_COMMAND: user_input.get(CONF_MUTE_ON_COMMAND, False),
                    },
                )

        device_names = [d.get("deviceName", d["deviceKey"]) for d in self._devices]

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(device_names),
                    vol.Required(CONF_MUTE_ON_COMMAND, default=False): bool,
                }
            ),
            errors=errors,
        )
