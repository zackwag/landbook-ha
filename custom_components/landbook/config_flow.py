"""Config flow for Landbook integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import LandbookAuthError, async_get_device_list, async_login
from .const import (
    CONF_BEARER_TOKEN,
    CONF_DEVICE_KEY,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_MUTE_ON_COMMAND,
    CONF_PASSWORD,
    CONF_PRODUCT_KEY,
    CONF_PRODUCT_NAME,
    CONF_UID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class LandbookOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Landbook integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MUTE_ON_COMMAND,
                        default=self.config_entry.options.get(CONF_MUTE_ON_COMMAND, False),
                    ): bool,
                }
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
        self._devices: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: collect email + password, attempt login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            try:
                bearer_token, uid = await async_login(email, password)
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
                return await self.async_step_pick_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: pick which device to add."""
        errors: dict[str, str] = {}

        if not self._devices:
            try:
                self._devices = await async_get_device_list(self._bearer_token)
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
                await self.async_set_unique_id(
                    f"{DOMAIN}_{device['deviceKey']}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device["deviceName"],
                    data={
                        CONF_EMAIL: self._email,
                        CONF_BEARER_TOKEN: self._bearer_token,
                        CONF_UID: self._uid,
                        CONF_DEVICE_KEY: device["deviceKey"],
                        CONF_PRODUCT_KEY: device["productKey"],
                        CONF_DEVICE_NAME: device["deviceName"],
                        CONF_PRODUCT_NAME: device.get("productName", ""),
                    },
                )

        device_names = [d.get("deviceName", d["deviceKey"]) for d in self._devices]

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_names)}
            ),
            errors=errors,
        )
