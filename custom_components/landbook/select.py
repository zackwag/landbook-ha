"""Select entities for ENUM/BOOL-typed Landbook extra properties."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
        LandbookSelect(hass, entry, data, prop)
        for prop in data["extra_props"]
        if prop["dataType"] in ("ENUM", "BOOL")
    ]
    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookSelect(SelectEntity):
    """A select entity for an ENUM or BOOL TSL property."""

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
        dtype = prop["dataType"]

        # Build label -> raw_value map
        if dtype == "BOOL":
            specs = prop.get("specs") or []
            self._options_map: dict[str, Any] = {
                s["name"]: (s["value"] == "true") for s in specs
            }
        else:  # ENUM
            self._options_map = {
                s["name"]: int(s["value"])
                for s in (prop.get("specs") or [])
            }

        self._attr_options = list(self._options_map.keys())
        self._attr_current_option = self._attr_options[0] if self._attr_options else None

        device_name: str = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} {prop['name']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
        )

    async def async_select_option(self, option: str) -> None:
        if option not in self._options_map:
            return
        self._attr_current_option = option
        self._data["mqtt_client"].send_write(
            self._data["device_id"],
            self._data["pk"],
            self._data["dk"],
            {self._code: self._options_map[option]},
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_state_update_{self._entry.entry_id}",
                self._handle_state_update,
            )
        )

    @callback
    def _handle_state_update(self, event: Event) -> None:
        raw = self._data["state"].get(self._code)
        if raw is None:
            return
        # Reverse-lookup the label for the raw value
        for label, val in self._options_map.items():
            if val == raw:
                self._attr_current_option = label
                self.async_write_ha_state()
                return
