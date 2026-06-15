"""Light entities for display-type BOOL Landbook properties."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LandbookLight(hass, entry, data, prop)
        for prop in data.get("light_props", [])
    ]
    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookLight(LightEntity):
    """A light entity for a display/backlight BOOL TSL property."""

    _attr_should_poll = False
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

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
        self._attr_is_on: bool = False

        device_name: str = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} Device Display"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
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
        raw = self._data["state"].get(self._code)
        if raw is not None:
            self._attr_is_on = bool(raw)
            self.async_write_ha_state()
