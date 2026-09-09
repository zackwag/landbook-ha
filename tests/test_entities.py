"""Tests for entity availability, state updates, and platform-specific logic.

Covers light, switch, number, sensor, and select entities.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.landbook.light import LandbookLight
from custom_components.landbook.switch import LandbookSwitch
from custom_components.landbook.number import LandbookNumber
from custom_components.landbook.sensor import LandbookTemperatureSensor
from custom_components.landbook.select import LandbookCountdown, LandbookSelect, _countdown_label


def _patch_entity(entity):
    """Set hass and stub async_write_ha_state so the entity works outside HA."""
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(**overrides):
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "device_name": "Test Fan",
        "product_name": "Test Product",
        "fw_version": "1.0",
        **overrides.pop("data", {}),
    }
    entry.options = overrides.pop("options", {})
    return entry


def _make_data(state=None, online=True, power_on=True):
    return {
        "power_prop": {"code": "power"},
        "state": {"power": power_on, **(state or {})},
        "online": online,
        "mqtt_client": MagicMock(),
        "device_id": "qdpk1dk1",
        "pk": "pk1",
        "dk": "dk1",
    }


def _event(changed_keys):
    ev = MagicMock()
    ev.data = {"changed_keys": set(changed_keys)}
    return ev


# ---------------------------------------------------------------------------
# Availability (shared pattern: offline=unavailable, power off=unavailable)
# ---------------------------------------------------------------------------

class TestAvailabilityGating:
    """Light, switch, number, select, countdown all gate on online + power."""

    @pytest.mark.parametrize("cls,prop", [
        (LandbookLight, {"code": "light", "name": "Light", "dataType": "BOOL"}),
        (LandbookSwitch, {"code": "sound", "name": "Sound", "dataType": "BOOL",
                          "specs": [{"name": "On", "value": "true"}, {"name": "Off", "value": "false"}]}),
        (LandbookNumber, {"code": "brightness", "name": "Brightness", "dataType": "INT",
                          "specs": {"min": "0", "max": "100", "step": "1"}}),
    ])
    def test_available_when_online_and_power_on(self, cls, prop):
        entity = cls(MagicMock(), _make_entry(), _make_data(power_on=True), prop)
        assert entity.available is True

    @pytest.mark.parametrize("cls,prop", [
        (LandbookLight, {"code": "light", "name": "Light", "dataType": "BOOL"}),
        (LandbookSwitch, {"code": "sound", "name": "Sound", "dataType": "BOOL",
                          "specs": [{"name": "On", "value": "true"}, {"name": "Off", "value": "false"}]}),
        (LandbookNumber, {"code": "brightness", "name": "Brightness", "dataType": "INT",
                          "specs": {"min": "0", "max": "100", "step": "1"}}),
    ])
    def test_unavailable_when_offline(self, cls, prop):
        entity = cls(MagicMock(), _make_entry(), _make_data(online=False), prop)
        assert entity.available is False

    @pytest.mark.parametrize("cls,prop", [
        (LandbookLight, {"code": "light", "name": "Light", "dataType": "BOOL"}),
        (LandbookSwitch, {"code": "sound", "name": "Sound", "dataType": "BOOL",
                          "specs": [{"name": "On", "value": "true"}, {"name": "Off", "value": "false"}]}),
        (LandbookNumber, {"code": "brightness", "name": "Brightness", "dataType": "INT",
                          "specs": {"min": "0", "max": "100", "step": "1"}}),
    ])
    def test_unavailable_when_power_off(self, cls, prop):
        entity = cls(MagicMock(), _make_entry(), _make_data(power_on=False), prop)
        assert entity.available is False


# ---------------------------------------------------------------------------
# Temperature sensor
# ---------------------------------------------------------------------------

class TestTemperatureSensor:
    def _make_sensor(self, use_celsius=False):
        options = {"temperature_unit": "°C"} if use_celsius else {}
        entry = _make_entry(options=options)
        data = _make_data()
        prop = {"code": "temperature", "name": "Temperature", "dataType": "INT"}
        sensor = LandbookTemperatureSensor(MagicMock(), entry, data, prop)
        _patch_entity(sensor)
        return sensor, data

    def test_convert_fahrenheit_passthrough(self):
        sensor, _ = self._make_sensor(use_celsius=False)
        assert sensor._convert(72.0) == 72.0

    def test_convert_to_celsius(self):
        sensor, _ = self._make_sensor(use_celsius=True)
        assert sensor._convert(72.0) == 22.2

    def test_convert_freezing_point(self):
        sensor, _ = self._make_sensor(use_celsius=True)
        assert sensor._convert(32.0) == 0.0

    def test_convert_boiling_point(self):
        sensor, _ = self._make_sensor(use_celsius=True)
        assert sensor._convert(212.0) == 100.0

    def test_state_update_sets_value(self):
        sensor, data = self._make_sensor()
        data["state"]["temperature"] = 75
        sensor._handle_state_update(_event(["temperature"]))
        assert sensor._attr_native_value == 75.0

    def test_state_update_ignores_irrelevant_key(self):
        sensor, data = self._make_sensor()
        sensor._attr_native_value = 70.0
        data["state"]["speed"] = 5
        sensor._handle_state_update(_event(["speed"]))
        assert sensor._attr_native_value == 70.0

    def test_available_always_when_online(self):
        sensor, data = self._make_sensor()
        data["online"] = True
        assert sensor.available is True

    def test_unavailable_when_offline(self):
        sensor, data = self._make_sensor()
        data["online"] = False
        assert sensor.available is False


# ---------------------------------------------------------------------------
# _countdown_label (pure function)
# ---------------------------------------------------------------------------

class TestCountdownLabel:
    def test_zero_is_cancel(self):
        assert _countdown_label(0) == "Cancel"

    def test_one_hour(self):
        assert _countdown_label(1) == "1 h"

    def test_twelve_hours(self):
        assert _countdown_label(12) == "12 h"


# ---------------------------------------------------------------------------
# Countdown select entity
# ---------------------------------------------------------------------------

class TestCountdownEntity:
    def _make_countdown(self, power_on=True):
        entry = _make_entry()
        data = _make_data(power_on=power_on)
        prop = {"code": "countdown", "name": "Countdown", "dataType": "ENUM",
                "specs": [
                    {"name": "0", "value": "0"},
                    {"name": "1", "value": "1"},
                    {"name": "2", "value": "2"},
                    {"name": "4", "value": "4"},
                ]}
        cd = LandbookCountdown(MagicMock(), entry, data, prop)
        _patch_entity(cd)
        return cd, data

    def test_options_generated(self):
        cd, _ = self._make_countdown()
        assert cd._attr_options == ["Cancel", "1 h", "2 h", "4 h"]

    def test_state_update_sets_option(self):
        cd, data = self._make_countdown()
        data["state"]["countdown"] = 2
        cd._handle_state_update(_event(["countdown"]))
        assert cd._attr_current_option == "2 h"

    def test_state_update_cancel(self):
        cd, data = self._make_countdown()
        cd._attr_current_option = "2 h"
        data["state"]["countdown"] = 0
        cd._handle_state_update(_event(["countdown"]))
        assert cd._attr_current_option == "Cancel"

    def test_unavailable_when_power_off(self):
        cd, _ = self._make_countdown(power_on=False)
        assert cd.available is False

    def test_available_when_power_on(self):
        cd, _ = self._make_countdown(power_on=True)
        assert cd.available is True


# ---------------------------------------------------------------------------
# Generic select entity
# ---------------------------------------------------------------------------

class TestGenericSelect:
    def _make_select(self, power_on=True):
        entry = _make_entry()
        data = _make_data(power_on=power_on)
        prop = {"code": "custom_mode", "name": "Custom", "dataType": "ENUM",
                "specs": [
                    {"name": "Low", "value": "0"},
                    {"name": "Medium", "value": "1"},
                    {"name": "High", "value": "2"},
                ]}
        sel = LandbookSelect(MagicMock(), entry, data, prop)
        _patch_entity(sel)
        return sel, data

    def test_reverse_lookup_int_to_label(self):
        sel, data = self._make_select()
        data["state"]["custom_mode"] = 1
        sel._handle_state_update(_event(["custom_mode"]))
        assert sel._attr_current_option == "Medium"

    def test_reverse_lookup_string_int(self):
        sel, data = self._make_select()
        data["state"]["custom_mode"] = "2"
        sel._handle_state_update(_event(["custom_mode"]))
        assert sel._attr_current_option == "High"

    def test_ignores_irrelevant_key(self):
        sel, data = self._make_select()
        sel._attr_current_option = "Low"
        sel._handle_state_update(_event(["unrelated"]))
        assert sel._attr_current_option == "Low"


# ---------------------------------------------------------------------------
# Light state updates
# ---------------------------------------------------------------------------

class TestLightEntity:
    def _make_light(self):
        entry = _make_entry()
        data = _make_data()
        prop = {"code": "light", "name": "Light", "dataType": "BOOL"}
        light = LandbookLight(MagicMock(), entry, data, prop)
        _patch_entity(light)
        return light, data

    def test_state_update_on(self):
        light, data = self._make_light()
        data["state"]["light"] = True
        light._handle_state_update(_event(["light"]))
        assert light._attr_is_on is True

    def test_state_update_off(self):
        light, data = self._make_light()
        light._attr_is_on = True
        data["state"]["light"] = False
        light._handle_state_update(_event(["light"]))
        assert light._attr_is_on is False


# ---------------------------------------------------------------------------
# Switch state updates
# ---------------------------------------------------------------------------

class TestSwitchEntity:
    def _make_switch(self):
        entry = _make_entry()
        data = _make_data()
        prop = {"code": "sound", "name": "Sound", "dataType": "BOOL",
                "specs": [{"name": "On", "value": "true"}, {"name": "Off", "value": "false"}]}
        sw = LandbookSwitch(MagicMock(), entry, data, prop)
        _patch_entity(sw)
        return sw, data

    def test_state_update_on(self):
        sw, data = self._make_switch()
        data["state"]["sound"] = True
        sw._handle_state_update(_event(["sound"]))
        assert sw._attr_is_on is True

    def test_state_update_off(self):
        sw, data = self._make_switch()
        sw._attr_is_on = True
        data["state"]["sound"] = False
        sw._handle_state_update(_event(["sound"]))
        assert sw._attr_is_on is False


# ---------------------------------------------------------------------------
# Number state updates
# ---------------------------------------------------------------------------

class TestNumberEntity:
    def _make_number(self):
        entry = _make_entry()
        data = _make_data()
        prop = {"code": "brightness", "name": "Brightness", "dataType": "INT",
                "specs": {"min": "0", "max": "100", "step": "1"}}
        num = LandbookNumber(MagicMock(), entry, data, prop)
        _patch_entity(num)
        return num, data

    def test_state_update(self):
        num, data = self._make_number()
        data["state"]["brightness"] = 75
        num._handle_state_update(_event(["brightness"]))
        assert num._attr_native_value == 75.0

    def test_min_max_from_specs(self):
        num, _ = self._make_number()
        assert num._attr_native_min_value == 0.0
        assert num._attr_native_max_value == 100.0
        assert num._attr_native_step == 1.0
