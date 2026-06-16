"""Sensor entities for Landbook devices."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, CONF_FW_VERSION, CONF_PRODUCT_NAME, CONF_TEMP_UNIT, DOMAIN, TEMP_UNIT_C, TEMP_UNIT_F

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []

    temp_prop = data.get("temperature_prop")
    if temp_prop:
        entities.append(LandbookTemperatureSensor(hass, entry, data, temp_prop))

    if entities:
        async_add_entities(entities, update_before_add=False)


class LandbookTemperatureSensor(SensorEntity):
    """Temperature sensor sourced from bus_ MQTT reports."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        self._attr_native_value: float | None = None

        device_name: str = entry.data[CONF_DEVICE_NAME]
        product_name: str = entry.data.get(CONF_PRODUCT_NAME, "")
        fw_version: str | None = entry.data.get(CONF_FW_VERSION)
        self._attr_unique_id = f"{entry.entry_id}_{self._code}"
        self._attr_name = f"{device_name} Temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Landbook",
            model=product_name or None,
            sw_version=fw_version,
        )

    @property
    def _use_celsius(self) -> bool:
        unit = self._entry.options.get(
            CONF_TEMP_UNIT,
            self._entry.data.get(CONF_TEMP_UNIT, TEMP_UNIT_F),
        )
        return unit == TEMP_UNIT_C

    @property
    def native_unit_of_measurement(self) -> str:
        return UnitOfTemperature.CELSIUS if self._use_celsius else UnitOfTemperature.FAHRENHEIT

    @property
    def available(self) -> bool:
        return self._data.get("online", True)

    def _convert(self, raw_f: float) -> float:
        if self._use_celsius:
            return round((raw_f - 32) * 5 / 9, 1)
        return raw_f

    async def async_added_to_hass(self) -> None:
        raw = self._data["state"].get(self._code)
        if raw is not None:
            try:
                self._attr_native_value = self._convert(float(raw))
            except (ValueError, TypeError):
                pass

        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_state_update_{self._entry.entry_id}",
                self._handle_state_update,
            )
        )

    @callback
    def _handle_state_update(self, event: Event) -> None:
        changed: set[str] = event.data.get("changed_keys", set()) if event else set()
        if changed and self._code not in changed:
            return
        raw = self._data["state"].get(self._code)
        if raw is not None:
            try:
                self._attr_native_value = self._convert(float(raw))
                self.async_write_ha_state()
            except (ValueError, TypeError):
                _LOGGER.warning("Unexpected temperature value: %r", raw)
