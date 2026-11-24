"""Failed or cancelled setup must dispose of its unpublished MQTT client."""

import asyncio
import threading

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.landbook import async_setup_entry
from custom_components.landbook.const import DOMAIN

from .conftest import make_config_entry, make_hass, register_entry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [ConnectionError("refused"), OSError("network"), ValueError("setup")]
)
async def test_failed_connect_disposes_unpublished_client(mock_landbook_api, error):
    hass = make_hass()
    entry = make_config_entry(hass)
    register_entry(hass, entry)
    mock_landbook_api.mqtt.connect.side_effect = error
    expected = ConfigEntryNotReady if isinstance(error, ConnectionError) else type(error)

    with pytest.raises(expected):
        await async_setup_entry(hass, entry)

    mock_landbook_api.mqtt.disconnect.assert_called_once()
    assert "u1" not in hass.data[DOMAIN].get("_accounts", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("connect_fails", [False, True])
@pytest.mark.parametrize("repeat_cancel", [False, True])
async def test_cancelled_setup_closes_client_after_executor_finishes(
    mock_landbook_api, connect_fails, repeat_cancel
):
    hass = make_hass()
    entry = make_config_entry(hass)
    register_entry(hass, entry)
    started = threading.Event()
    release = threading.Event()
    events = []

    def connect():
        started.set()
        assert release.wait(timeout=5)
        events.append("connect finished")
        if connect_fails:
            raise ConnectionError("late failure")

    mock_landbook_api.mqtt.connect.side_effect = connect
    mock_landbook_api.mqtt.disconnect.side_effect = lambda: events.append("disconnected")
    hass.async_add_executor_job = lambda fn, *args: asyncio.create_task(
        asyncio.to_thread(fn, *args)
    )
    cleanup_started = asyncio.Event()
    cleanup_tasks = []

    def create_cleanup(coro):
        task = asyncio.create_task(coro)
        cleanup_tasks.append(task)
        cleanup_started.set()
        return task

    hass.async_create_task.side_effect = create_cleanup
    setup_task = asyncio.create_task(async_setup_entry(hass, entry))
    try:
        assert await asyncio.to_thread(started.wait, 3)
        setup_task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), timeout=3)
        if repeat_cancel:
            setup_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await setup_task
        mock_landbook_api.mqtt.disconnect.assert_not_called()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(setup_task, timeout=3)
        await asyncio.wait_for(asyncio.gather(*cleanup_tasks), timeout=3)
        assert events == ["connect finished", "disconnected"]
        assert "u1" not in hass.data[DOMAIN].get("_accounts", {})
    finally:
        release.set()
        if not setup_task.done():
            setup_task.cancel()
            await asyncio.gather(setup_task, return_exceptions=True)
