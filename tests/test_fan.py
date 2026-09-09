"""Tests for the LandbookFan entity."""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.fan import FanEntityFeature

from custom_components.landbook.fan import LandbookFan, _suggest_area


# ---------------------------------------------------------------------------
# _suggest_area (pure function)
# ---------------------------------------------------------------------------

class TestSuggestArea:
    def test_strips_product_trailing_words(self):
        assert _suggest_area("Living Room Fan", "OmniBreeze Tower Fan") == "Living Room"

    def test_strips_all_matching_words(self):
        assert _suggest_area("Bedroom Tower Fan", "OmniBreeze Tower Fan") == "Bedroom"

    def test_no_product_name(self):
        assert _suggest_area("My Fan", "") is None

    def test_all_words_match_product(self):
        assert _suggest_area("Fan", "OmniBreeze Tower Fan") is None

    def test_single_word_remaining(self):
        assert _suggest_area("Kitchen Fan", "Tower Fan") == "Kitchen"

    def test_case_insensitive(self):
        assert _suggest_area("Office FAN", "tower fan") == "Office"


# ---------------------------------------------------------------------------
# Fan entity helpers
# ---------------------------------------------------------------------------

def _make_fan(
    speed_count=12,
    preset_modes=None,
    has_oscillation=True,
    power_code="power",
):
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "device_name": "Test Fan",
        "product_name": "Test Product",
        "fw_version": "1.0",
    }

    power_prop = {"code": power_code, "dataType": "BOOL", "sort": 0,
                  "specs": [{"name": "On", "value": "true"}]}
    speed_prop = {"code": "speed", "dataType": "INT",
                  "specs": {"min": "1", "max": str(speed_count), "step": "1"}}
    mode_prop = None
    oscillation_prop = None

    if preset_modes:
        mode_prop = {"code": "mode", "dataType": "ENUM", "specs": [
            {"name": name, "value": str(i)} for i, name in enumerate(preset_modes)
        ]}

    if has_oscillation:
        oscillation_prop = {"code": "oscillate", "dataType": "BOOL"}

    data = {
        "power_prop": power_prop,
        "speed_prop": speed_prop,
        "mode_prop": mode_prop,
        "oscillation_prop": oscillation_prop,
        "state": {},
        "online": True,
        "mqtt_client": MagicMock(),
        "device_id": "qdpk1dk1",
        "pk": "pk1",
        "dk": "dk1",
    }

    hass = MagicMock()
    fan = LandbookFan(hass, entry, data)
    fan.hass = hass
    fan.async_write_ha_state = MagicMock()
    return fan, data


# ---------------------------------------------------------------------------
# Supported features
# ---------------------------------------------------------------------------

def _ensure_turn_on_off():
    """Add TURN_ON/TURN_OFF to FanEntityFeature if the HA version predates them."""
    if not hasattr(FanEntityFeature, "TURN_ON"):
        FanEntityFeature.TURN_ON = FanEntityFeature(16)
    if not hasattr(FanEntityFeature, "TURN_OFF"):
        FanEntityFeature.TURN_OFF = FanEntityFeature(32)


class TestSupportedFeatures:
    def test_speed_and_preset_and_oscillation(self):
        _ensure_turn_on_off()
        fan, _ = _make_fan(preset_modes=["Normal", "Auto"])
        features = fan.supported_features
        assert features & FanEntityFeature.SET_SPEED
        assert features & FanEntityFeature.PRESET_MODE
        assert features & FanEntityFeature.OSCILLATE

    def test_no_oscillation(self):
        _ensure_turn_on_off()
        fan, _ = _make_fan(has_oscillation=False)
        assert not (fan.supported_features & FanEntityFeature.OSCILLATE)

    def test_no_preset_modes(self):
        _ensure_turn_on_off()
        fan, _ = _make_fan(preset_modes=None)
        assert not (fan.supported_features & FanEntityFeature.PRESET_MODE)


# ---------------------------------------------------------------------------
# Speed percentage math
# ---------------------------------------------------------------------------

class TestSpeedPercentage:
    def test_speed_1_of_12(self):
        fan, _ = _make_fan(speed_count=12)
        fan._current_speed_idx = 0
        fan._is_on = True
        pct = fan.percentage
        assert pct == round(1 / 12 * 100)

    def test_speed_12_of_12(self):
        fan, _ = _make_fan(speed_count=12)
        fan._current_speed_idx = 11
        fan._is_on = True
        assert fan.percentage == 100

    def test_speed_6_of_12(self):
        fan, _ = _make_fan(speed_count=12)
        fan._current_speed_idx = 5
        fan._is_on = True
        assert fan.percentage == 50

    def test_auto_mode_returns_none(self):
        fan, _ = _make_fan(preset_modes=["Normal", "Auto"])
        fan._current_mode_idx = 1  # Auto
        fan._is_on = True
        assert fan.percentage is None

    def test_speed_count(self):
        fan, _ = _make_fan(speed_count=12)
        assert fan.speed_count == 12


# ---------------------------------------------------------------------------
# _is_auto_mode
# ---------------------------------------------------------------------------

class TestIsAutoMode:
    def test_auto_detected(self):
        fan, _ = _make_fan(preset_modes=["Normal", "Natural", "Sleep", "Auto"])
        fan._current_mode_idx = 3
        assert fan._is_auto_mode() is True

    def test_non_auto_mode(self):
        fan, _ = _make_fan(preset_modes=["Normal", "Natural", "Sleep", "Auto"])
        fan._current_mode_idx = 0
        assert fan._is_auto_mode() is False

    def test_no_modes(self):
        fan, _ = _make_fan(preset_modes=None)
        assert fan._is_auto_mode() is False

    def test_out_of_bounds_index(self):
        fan, _ = _make_fan(preset_modes=["Normal"])
        fan._current_mode_idx = 99
        assert fan._is_auto_mode() is False


# ---------------------------------------------------------------------------
# State update handler
# ---------------------------------------------------------------------------

class TestHandleStateUpdate:
    def test_power_on_from_mqtt(self):
        fan, data = _make_fan()
        data["state"]["power"] = True
        event = MagicMock()
        event.data = {"changed_keys": {"power"}}
        fan._handle_state_update(event)
        assert fan._is_on is True

    def test_power_off_from_mqtt(self):
        fan, data = _make_fan()
        fan._is_on = True
        data["state"]["power"] = False
        event = MagicMock()
        event.data = {"changed_keys": {"power"}}
        fan._handle_state_update(event)
        assert fan._is_on is False

    def test_speed_update(self):
        fan, data = _make_fan(speed_count=12)
        data["state"]["speed"] = 6
        event = MagicMock()
        event.data = {"changed_keys": {"speed"}}
        fan._handle_state_update(event)
        assert fan._current_speed_idx == 5  # 0-indexed

    def test_mode_update(self):
        fan, data = _make_fan(preset_modes=["Normal", "Natural", "Sleep", "Auto"])
        data["state"]["mode"] = 2
        event = MagicMock()
        event.data = {"changed_keys": {"mode"}}
        fan._handle_state_update(event)
        assert fan._current_mode_idx == 2
        assert fan.preset_mode == "Sleep"

    def test_oscillation_update(self):
        fan, data = _make_fan()
        data["state"]["oscillate"] = True
        event = MagicMock()
        event.data = {"changed_keys": {"oscillate"}}
        fan._handle_state_update(event)
        assert fan._oscillating is True

    def test_ignores_irrelevant_keys(self):
        fan, data = _make_fan()
        fan._is_on = False
        data["state"]["unrelated"] = 42
        event = MagicMock()
        event.data = {"changed_keys": {"unrelated"}}
        fan._handle_state_update(event)
        assert fan._is_on is False

    def test_initial_update_no_event(self):
        fan, data = _make_fan()
        data["state"]["power"] = True
        data["state"]["speed"] = 3
        fan._handle_state_update(None)
        assert fan._is_on is True
        assert fan._current_speed_idx == 2


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_available_when_online(self):
        fan, data = _make_fan()
        data["online"] = True
        assert fan.available is True

    def test_unavailable_when_offline(self):
        fan, data = _make_fan()
        data["online"] = False
        assert fan.available is False
