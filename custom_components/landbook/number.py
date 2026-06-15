"""Number entities for INT-typed Landbook properties."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
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
        LandbookNumber(hass, entry, data, prop)
        for prop in data["extra_props"]
        if prop["dataType"] == "INT"
    ]
    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookNumber(NumberEntity):
    """A number entity for an INT TSL property."""

    _attr_should_poll = False
    _attr_mode = NumberMode.SLIDER

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

        specs = prop.get("specs", {})
        self._attr_native_min_value = float(specs.get("min", 0))
        self._attr_native_max_value = float(specs.get("max", 100))
        self._attr_native_step = float(specs.get("step", 1) or 1)
        self._attr_native_value = self._attr_native_min_value

        device_name: str = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} {prop['name']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
        )

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._data["mqtt_client"].send_write(
            self._data["device_id"],
            self._data["pk"],
            self._data["dk"],
            {self._code: int(value)},
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
        if raw is not None:
            self._attr_native_value = float(raw)
            self.async_write_ha_state()
