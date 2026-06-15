"""Switch entities for BOOL-typed Landbook extra properties."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, CONF_PRODUCT_NAME, DISPLAY_LIGHT_HINTS, DISPLAY_NAME_OVERRIDES, SWITCH_ICON_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LandbookSwitch(hass, entry, data, prop)
        for prop in data["extra_props"]
        if prop["dataType"] == "BOOL"
        and not any(
            hint in prop.get("name", "").lower() or hint in prop.get("code", "").lower()
            for hint in DISPLAY_LIGHT_HINTS
        )
    ]
    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookSwitch(SwitchEntity):
    """A switch entity for a BOOL TSL property."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        data: dict,
        prop: dict,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._data = data
        self._prop = prop
        self._code: str = prop["code"]

        # Resolve on/off values from specs (default True/False)
        specs = {s["name"].lower(): s["value"] for s in (prop.get("specs") or [])}
        self._on_value = specs.get("on", specs.get("open", specs.get("enable", "true"))) == "true"

        self._attr_is_on: bool = False

        device_name: str = entry.data[CONF_DEVICE_NAME]
        product_name: str = entry.data.get(CONF_PRODUCT_NAME, "")
        tsl_name: str = prop.get("name", self._code)
        display_name = DISPLAY_NAME_OVERRIDES.get(tsl_name.lower(), tsl_name)

        self._attr_icon = SWITCH_ICON_MAP.get(tsl_name.lower())
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} {display_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
            model=product_name or None,
        )

    @property
    def available(self) -> bool:
        return self._data.get("online", True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self._data["mqtt_client"].send_write(
            self._data["device_id"],
            self._data["pk"],
            self._data["dk"],
            {self._code: True},
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self._data["mqtt_client"].send_write(
            self._data["device_id"],
            self._data["pk"],
            self._data["dk"],
            {self._code: False},
        )
        self.async_write_ha_state()

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
        if changed and self._code not in changed:
            return
        raw = self._data["state"].get(self._code)
        if raw is not None:
            self._attr_is_on = bool(raw)
            self.async_write_ha_state()
