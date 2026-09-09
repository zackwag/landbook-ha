"""Tests for TSL property detection helpers in __init__.py."""
from __future__ import annotations

import pytest

from custom_components.landbook import (
    _coerce_value,
    _find_countdown_prop,
    _find_light_props,
    _find_mode_prop,
    _find_oscillation_prop,
    _find_power_prop,
    _find_speed_prop,
    _find_temperature_prop,
)


# ---------------------------------------------------------------------------
# Fixture: realistic TSL property list from DC2313R fan
# ---------------------------------------------------------------------------

def _make_prop(code, name, dtype, sort=99, specs=None):
    p = {"code": code, "name": name, "dataType": dtype, "sort": sort}
    if specs is not None:
        p["specs"] = specs
    return p


POWER = _make_prop("power", "Power", "BOOL", sort=0, specs=[
    {"name": "On", "value": "true"},
    {"name": "Off", "value": "false"},
])
SPEED = _make_prop("speed", "Wind Speed", "INT", sort=1, specs={"min": "1", "max": "12", "step": "1"})
MODE = _make_prop("mode", "Working Mode", "ENUM", sort=2, specs=[
    {"name": "Normal", "value": "0"},
    {"name": "Natural", "value": "1"},
    {"name": "Sleep", "value": "2"},
    {"name": "Auto", "value": "3"},
])
OSCILLATION = _make_prop("oscillate", "Oscillation", "BOOL", sort=3, specs=[
    {"name": "On", "value": "true"},
    {"name": "Off", "value": "false"},
])
LIGHT = _make_prop("light", "Light", "BOOL", sort=4, specs=[
    {"name": "On", "value": "true"},
    {"name": "Off", "value": "false"},
])
SOUND = _make_prop("sound", "Sound", "BOOL", sort=5, specs=[
    {"name": "On", "value": "true"},
    {"name": "Off", "value": "false"},
])
COUNTDOWN = _make_prop("countdown", "Countdown", "ENUM", sort=6, specs=[
    {"name": "0", "value": "0"},
    {"name": "1", "value": "1"},
    {"name": "2", "value": "2"},
])
TEMPERATURE = _make_prop("temperature", "Temperature", "INT", sort=7, specs={"min": "0", "max": "150"})

ALL_PROPS = [POWER, SPEED, MODE, OSCILLATION, LIGHT, SOUND, COUNTDOWN, TEMPERATURE]


# ---------------------------------------------------------------------------
# _find_power_prop
# ---------------------------------------------------------------------------

class TestFindPowerProp:
    def test_finds_by_sort_and_specs(self):
        assert _find_power_prop(ALL_PROPS) is POWER

    def test_fallback_to_first_bool_if_no_sort_match(self):
        generic_bool = _make_prop("toggle", "Toggle", "BOOL", sort=5)
        assert _find_power_prop([generic_bool]) is generic_bool

    def test_empty_list(self):
        assert _find_power_prop([]) is None

    def test_no_bool_props(self):
        assert _find_power_prop([SPEED, MODE]) is None


# ---------------------------------------------------------------------------
# _find_speed_prop
# ---------------------------------------------------------------------------

class TestFindSpeedProp:
    def test_finds_speed_by_name_hint(self):
        assert _find_speed_prop(ALL_PROPS, POWER) is SPEED

    def test_skips_power_prop(self):
        # Even if power were INT, it should be skipped
        fake_power = _make_prop("power", "Wind Speed", "INT")
        other = _make_prop("fan_speed", "Speed", "INT")
        assert _find_speed_prop([fake_power, other], fake_power) is other

    def test_no_speed_prop(self):
        assert _find_speed_prop([POWER, MODE], POWER) is None

    def test_matches_code_hint(self):
        prop = _make_prop("wind_level", "Setting", "INT")
        assert _find_speed_prop([prop], None) is prop


# ---------------------------------------------------------------------------
# _find_mode_prop
# ---------------------------------------------------------------------------

class TestFindModeProp:
    def test_finds_mode_by_name(self):
        assert _find_mode_prop(ALL_PROPS, POWER, SPEED) is MODE

    def test_skips_power_and_speed(self):
        result = _find_mode_prop([POWER, SPEED, MODE], POWER, SPEED)
        assert result is MODE

    def test_matches_working_hint(self):
        prop = _make_prop("work", "Working", "ENUM")
        assert _find_mode_prop([prop], None, None) is prop

    def test_no_mode_prop(self):
        assert _find_mode_prop([POWER, SPEED], POWER, SPEED) is None


# ---------------------------------------------------------------------------
# _find_oscillation_prop
# ---------------------------------------------------------------------------

class TestFindOscillationProp:
    def test_finds_oscillation(self):
        assert _find_oscillation_prop(ALL_PROPS, POWER, SPEED, MODE) is OSCILLATION

    def test_matches_swing_hint(self):
        prop = _make_prop("swing", "Swing", "BOOL")
        assert _find_oscillation_prop([prop], None, None) is prop

    def test_no_oscillation(self):
        assert _find_oscillation_prop([POWER, SPEED], POWER, SPEED) is None


# ---------------------------------------------------------------------------
# _find_light_props
# ---------------------------------------------------------------------------

class TestFindLightProps:
    def test_finds_light_prop(self):
        claimed = {id(POWER), id(SPEED), id(MODE), id(OSCILLATION)}
        result = _find_light_props(ALL_PROPS, claimed)
        assert LIGHT in result

    def test_excludes_claimed(self):
        claimed = {id(LIGHT)}
        result = _find_light_props([LIGHT], claimed)
        assert result == []

    def test_matches_display_hint(self):
        prop = _make_prop("screen_ctl", "Display", "BOOL")
        assert _find_light_props([prop], set()) == [prop]

    def test_ignores_non_bool(self):
        prop = _make_prop("backlight", "Backlight", "INT")
        assert _find_light_props([prop], set()) == []


# ---------------------------------------------------------------------------
# _find_temperature_prop
# ---------------------------------------------------------------------------

class TestFindTemperatureProp:
    def test_finds_real_temperature(self):
        claimed = {id(p) for p in [POWER, SPEED, MODE, OSCILLATION, LIGHT, SOUND, COUNTDOWN]}
        result = _find_temperature_prop(ALL_PROPS, claimed)
        assert result is TEMPERATURE

    def test_returns_synthetic_when_missing(self):
        result = _find_temperature_prop([POWER, SPEED], {id(POWER), id(SPEED)})
        assert result is not None
        assert result["synthetic"] is True
        assert result["code"] == "temperature"

    def test_matches_temp_hint(self):
        prop = _make_prop("env_temp", "Temp", "INT")
        assert _find_temperature_prop([prop], set()) is prop


# ---------------------------------------------------------------------------
# _find_countdown_prop
# ---------------------------------------------------------------------------

class TestFindCountdownProp:
    def test_finds_countdown(self):
        claimed = {id(p) for p in [POWER, SPEED, MODE, OSCILLATION, LIGHT, SOUND]}
        assert _find_countdown_prop(ALL_PROPS, claimed) is COUNTDOWN

    def test_matches_timer_hint(self):
        prop = _make_prop("sleep_timer", "Timer", "ENUM")
        assert _find_countdown_prop([prop], set()) is prop

    def test_ignores_non_enum(self):
        prop = _make_prop("countdown", "Countdown", "INT")
        assert _find_countdown_prop([prop], set()) is None

    def test_no_countdown(self):
        assert _find_countdown_prop([POWER], set()) is None


# ---------------------------------------------------------------------------
# _coerce_value
# ---------------------------------------------------------------------------

class TestCoerceValue:
    def test_none_passthrough(self):
        assert _coerce_value(None, "BOOL") is None
        assert _coerce_value(None, None) is None

    def test_bool_from_string(self):
        assert _coerce_value("true", "BOOL") is True
        assert _coerce_value("True", "BOOL") is True
        assert _coerce_value("false", "BOOL") is False
        assert _coerce_value("anything", "BOOL") is False

    def test_bool_from_bool(self):
        assert _coerce_value(True, "BOOL") is True
        assert _coerce_value(False, "BOOL") is False

    def test_int_from_string(self):
        assert _coerce_value("42", "INT") == 42

    def test_int_invalid_passthrough(self):
        assert _coerce_value("abc", "INT") == "abc"

    def test_enum_from_string(self):
        assert _coerce_value("3", "ENUM") == 3

    def test_enum_invalid_passthrough(self):
        assert _coerce_value("xyz", "ENUM") == "xyz"

    def test_unknown_dtype_passthrough(self):
        assert _coerce_value("hello", "STRING") == "hello"
        assert _coerce_value("hello", None) == "hello"
