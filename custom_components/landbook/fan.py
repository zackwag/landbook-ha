"""Fan entity for Landbook integration."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (CONF_DEVICE_NAME, CONF_FW_VERSION, CONF_PRODUCT_NAME,
                    CONF_RESTORE_STATE, DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LandbookFan(hass, entry, data)], update_before_add=False)


class LandbookFan(FanEntity):
    """Represents the Landbook fan device."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: dict) -> None:
        self._hass = hass
        self._entry = entry
        self._data = data
        self._power_prop = data["power_prop"]
        self._speed_prop = data["speed_prop"]       # INT → percentage
        self._mode_prop = data.get("mode_prop")     # ENUM → preset modes
        self._oscillation_prop = data.get("oscillation_prop")

        device_name: str = entry.data[CONF_DEVICE_NAME]
        product_name: str = entry.data.get(CONF_PRODUCT_NAME, "")
        fw_version: str | None = entry.data.get(CONF_FW_VERSION)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_name = device_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
            model=product_name or None,
            sw_version=fw_version,
            suggested_area=_suggest_area(device_name, product_name),
        )

        # Preset modes from ENUM mode prop
        self._preset_modes: list[str] = []
        self._mode_values: list[int] = []
        if self._mode_prop:
            for spec in (self._mode_prop.get("specs") or []):
                self._preset_modes.append(spec["name"])
                self._mode_values.append(int(spec["value"]))

        # Speed steps from INT speed prop
        self._speed_values: list[int] = []
        if self._speed_prop:
            specs = self._speed_prop.get("specs", {})
            lo = int(specs.get("min", 1))
            hi = int(specs.get("max", lo))
            step = int(specs.get("step", 1)) or 1
            self._speed_values = list(range(lo, hi + 1, step))

        self._is_on: bool = False
        self._oscillating: bool = False
        self._current_speed_idx: int = 0
        self._current_mode_idx: int = 0

    # ------------------------------------------------------------------
    # HA Fan API
    # ------------------------------------------------------------------

    @property
    def supported_features(self) -> FanEntityFeature:
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self._speed_values:
            features |= FanEntityFeature.SET_SPEED
        if self._preset_modes:
            features |= FanEntityFeature.PRESET_MODE
        if self._oscillation_prop:
            features |= FanEntityFeature.OSCILLATE
        return features

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def available(self) -> bool:
        return self._data.get("online", True)

    @property
    def oscillating(self) -> bool | None:
        if not self._oscillation_prop:
            return None
        return self._oscillating

    @property
    def percentage(self) -> int | None:
        if not self._speed_values:
            return None
        if self._current_speed_idx >= len(self._speed_values):
            return None
        if self._is_auto_mode():
            return None
        return round((self._current_speed_idx + 1) / len(self._speed_values) * 100)

    @property
    def speed_count(self) -> int:
        return len(self._speed_values) or 1

    @property
    def preset_modes(self) -> list[str] | None:
        return self._preset_modes if self._preset_modes else None

    @property
    def preset_mode(self) -> str | None:
        if not self._preset_modes:
            return None
        if self._current_mode_idx < len(self._preset_modes):
            return self._preset_modes[self._current_mode_idx]
        return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _restore_state_enabled(self) -> bool:
        return bool(self._entry.options.get(
            CONF_RESTORE_STATE,
            self._entry.data.get(CONF_RESTORE_STATE, False),
        ))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        props: dict = {}
        if self._power_prop:
            props[self._power_prop["code"]] = True

        if preset_mode and preset_mode in self._preset_modes:
            idx = self._preset_modes.index(preset_mode)
            props[self._mode_prop["code"]] = self._mode_values[idx]
            self._current_mode_idx = idx
        if percentage is not None and self._speed_values:
            idx = max(
                0,
                min(
                    len(self._speed_values) - 1,
                    math.ceil(percentage / 100 * len(self._speed_values)) - 1,
                ),
            )
            props[self._speed_prop["code"]] = self._speed_values[idx]
            self._current_speed_idx = idx

        if self._restore_state_enabled():
            preferred = self._data.get("preferred_state", {})
            for code, val in preferred.items():
                if code not in props:
                    props[code] = val

        self._is_on = True
        self._send(props)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not self._power_prop:
            return
        self._is_on = False
        self._send({self._power_prop["code"]: False})
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if not self._speed_values or self._is_auto_mode():
            return
        idx = max(
            0,
            min(
                len(self._speed_values) - 1,
                math.ceil(percentage / 100 * len(self._speed_values)) - 1,
            ),
        )
        self._current_speed_idx = idx
        self._send({self._speed_prop["code"]: self._speed_values[idx]})
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if not self._mode_prop or preset_mode not in self._preset_modes:
            return
        idx = self._preset_modes.index(preset_mode)
        self._current_mode_idx = idx
        self._send({self._mode_prop["code"]: self._mode_values[idx]})
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        if not self._oscillation_prop:
            return
        self._oscillating = oscillating
        self._send({self._oscillation_prop["code"]: oscillating})
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State updates from MQTT
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_state_update_{self._entry.entry_id}",
                self._handle_state_update,
            )
        )
        self._handle_state_update(None)

    @callback
    def _handle_state_update(self, event: Event) -> None:
        changed: set[str] = event.data.get("changed_keys", set()) if event else set()
        shared: dict = self._data["state"]
        updated = False

        if self._power_prop:
            code = self._power_prop["code"]
            if not changed or code in changed:
                raw = shared.get(code)
                if raw is not None:
                    was_on = self._is_on
                    self._is_on = bool(raw)
                    if was_on and not self._is_on and self._restore_state_enabled():
                        self._data["preferred_state"] = {
                            k: v for k, v in shared.items()
                            if k != code and v is not None
                        }
                    updated = True

        if self._speed_prop:
            code = self._speed_prop["code"]
            # Always sync speed — Auto mode can change it without a direct command
            raw = shared.get(code)
            if raw is not None:
                try:
                    val = int(raw)
                    if val in self._speed_values:
                        self._current_speed_idx = self._speed_values.index(val)
                        updated = True
                except (ValueError, TypeError):
                    pass

        if self._mode_prop:
            code = self._mode_prop["code"]
            # Always sync mode — device may change it autonomously
            raw = shared.get(code)
            if raw is not None:
                try:
                    val = int(raw)
                    if val in self._mode_values:
                        self._current_mode_idx = self._mode_values.index(val)
                        updated = True
                except (ValueError, TypeError):
                    pass

        if self._oscillation_prop:
            code = self._oscillation_prop["code"]
            if not changed or code in changed:
                raw = shared.get(code)
                if raw is not None:
                    self._oscillating = bool(raw)
                    updated = True

        if updated or not changed:
            self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_auto_mode(self) -> bool:
        if not self._preset_modes or self._current_mode_idx >= len(self._preset_modes):
            return False
        return self._preset_modes[self._current_mode_idx].lower() == "auto"

    def _send(self, props: dict) -> None:
        self._data["mqtt_client"].send_write(
            self._data["device_id"],
            self._data["pk"],
            self._data["dk"],
            props,
        )


def _suggest_area(device_name: str, product_name: str) -> str | None:
    """Derive a suggested area from the device name by removing the product name suffix."""
    if not product_name:
        return None
    # e.g. "Living Room Fan" with product "OmniBreeze Tower Fan" → strip last word "Fan"
    # More reliably: strip any trailing words that appear in the product name
    product_words = {w.lower() for w in product_name.split()}
    parts = device_name.split()
    # Drop trailing words that match product name words
    while parts and parts[-1].lower() in product_words:
        parts.pop()
    area = " ".join(parts).strip()
    return area or None
