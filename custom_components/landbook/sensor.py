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

from .const import CONF_DEVICE_NAME, CONF_FW_VERSION, CONF_PRODUCT_NAME, DOMAIN

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
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

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
    def available(self) -> bool:
        return self._data.get("online", True)

    async def async_added_to_hass(self) -> None:
        # Seed from initial state if already present
        raw = self._data["state"].get(self._code)
        if raw is not None:
            try:
                self._attr_native_value = float(raw)
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
                self._attr_native_value = float(raw)
                self.async_write_ha_state()
            except (ValueError, TypeError):
                _LOGGER.warning("Unexpected temperature value: %r", raw)
