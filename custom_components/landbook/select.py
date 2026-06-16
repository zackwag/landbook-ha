"""Select entities for ENUM-typed Landbook extra properties."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, CONF_FW_VERSION, CONF_PRODUCT_NAME, DISPLAY_NAME_OVERRIDES, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _countdown_label(minutes: int) -> str:
    if minutes == 0:
        return "Off"
    return f"{minutes} min"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []

    countdown_prop = data.get("countdown_prop")
    if countdown_prop:
        entities.append(LandbookCountdown(hass, entry, data, countdown_prop))

    entities += [
        LandbookSelect(hass, entry, data, prop)
        for prop in data["extra_props"]
        if prop["dataType"] == "ENUM"
    ]

    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookCountdown(SelectEntity):
    """Select entity for the countdown timer, with human-readable minute labels."""

    _attr_should_poll = False
    _attr_icon = "mdi:timer-outline"

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
        self._code: str = prop["code"]

        # Map "X min" / "Off" -> raw int value
        self._options_map: dict[str, int] = {
            _countdown_label(int(s["value"])): int(s["value"])
            for s in (prop.get("specs") or [])
        }

        self._attr_options = list(self._options_map.keys())
        self._attr_current_option = self._attr_options[0] if self._attr_options else None

        device_name: str = entry.data[CONF_DEVICE_NAME]
        product_name: str = entry.data.get(CONF_PRODUCT_NAME, "")
        fw_version: str | None = entry.data.get(CONF_FW_VERSION)
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} Countdown"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
            model=product_name or None,
            sw_version=fw_version,
        )

    @property
    def available(self) -> bool:
        return self._data.get("online", True)

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
        self._handle_state_update(None)

    @callback
    def _handle_state_update(self, event: Event) -> None:
        changed: set[str] = event.data.get("changed_keys", set()) if event else set()
        if changed and self._code not in changed:
            return
        raw = self._data["state"].get(self._code)
        if raw is None:
            return
        try:
            label = _countdown_label(int(raw))
            if label in self._options_map:
                self._attr_current_option = label
                self.async_write_ha_state()
        except (ValueError, TypeError):
            pass


class LandbookSelect(SelectEntity):
    """A select entity for an ENUM TSL property."""

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

        self._options_map: dict[str, int] = {
            s["name"]: int(s["value"])
            for s in (prop.get("specs") or [])
        }

        self._attr_options = list(self._options_map.keys())
        self._attr_current_option = self._attr_options[0] if self._attr_options else None

        device_name: str = entry.data[CONF_DEVICE_NAME]
        product_name: str = entry.data.get(CONF_PRODUCT_NAME, "")
        tsl_name: str = prop.get("name", self._code)
        display_name = DISPLAY_NAME_OVERRIDES.get(tsl_name.lower(), tsl_name)

        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} {display_name}"
        fw_version: str | None = entry.data.get(CONF_FW_VERSION)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
            model=product_name or None,
            sw_version=fw_version,
        )

    @property
    def available(self) -> bool:
        return self._data.get("online", True)

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
        self._handle_state_update(None)

    @callback
    def _handle_state_update(self, event: Event) -> None:
        changed: set[str] = event.data.get("changed_keys", set()) if event else set()
        if changed and self._code not in changed:
            return
        raw = self._data["state"].get(self._code)
        if raw is None:
            return
        try:
            raw_int = int(raw)
        except (ValueError, TypeError):
            raw_int = raw
        for label, val in self._options_map.items():
            if val == raw_int:
                self._attr_current_option = label
                self.async_write_ha_state()
                return
