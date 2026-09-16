"""Tests for the _ResilientMQTTClient write deferral.

landbook_api's send_write raises ConnectionError("MQTT not connected") when
the broker connection is momentarily down (for example during the 90-minute
token-rotation reconnect). That surfaces as a failed service call and the tap
is lost. The integration's _ResilientMQTTClient subclass parks such writes and
flushes them on reconnect, dropping anything queued longer than
_WRITE_RETRY_WINDOW so a tap during a long outage is not applied minutes later.
"""
from __future__ import annotations

import threading
from unittest.mock import patch

from landbook_api import LandbookMQTTClient

from custom_components.landbook import _WRITE_RETRY_WINDOW, _ResilientMQTTClient


class TestResilientMQTTClient:
    """_ResilientMQTTClient must queue writes across a brief disconnect."""

    def _make_client(self, sends, connected=True):
        """Build a _ResilientMQTTClient wired to a controllable fake parent.

        The parent LandbookMQTTClient.send_write is patched for the duration of
        the test: it raises ConnectionError while ``state["connected"]`` is
        False or while a device key is in ``state["down_dks"]``, otherwise it
        records the write. Returns (client, state, patch_context).
        """
        state = {"connected": connected, "down_dks": set()}

        def _parent_send(_self, device_id, pk, dk, props):
            if not state["connected"] or dk in state["down_dks"]:
                raise ConnectionError("MQTT not connected")
            sends.append((device_id, pk, dk, props))

        client = _ResilientMQTTClient.__new__(_ResilientMQTTClient)
        client._write_lock = threading.Lock()
        client._deferred_writes = []
        return (
            client,
            state,
            patch.object(LandbookMQTTClient, "send_write", new=_parent_send),
        )

    def test_write_while_connected_passes_through(self):
        """A write made while connected is forwarded immediately, not queued."""
        sends = []
        client, _state, parent_patch = self._make_client(sends, connected=True)
        with parent_patch:
            client.send_write("dev1", "pk", "dk1", {"switch": True})
        assert sends == [("dev1", "pk", "dk1", {"switch": True})]
        assert client._deferred_writes == []

    def test_write_while_disconnected_is_deferred_not_raised(self):
        """send_write must not raise when the connection is down; it queues."""
        sends = []
        client, _state, parent_patch = self._make_client(sends, connected=False)
        with parent_patch:
            client.send_write("dev1", "pk", "dk1", {"switch": True})
        assert sends == []
        assert len(client._deferred_writes) == 1

    def test_flush_resends_deferred_writes_in_order_on_reconnect(self):
        """Deferred writes are resent in order after reconnect, exactly once."""
        sends = []
        client, state, parent_patch = self._make_client(sends, connected=False)
        with parent_patch:
            client.send_write("dev1", "pk", "dk1", {"switch": True})
            client.send_write("dev1", "pk", "dk1", {"speed": 5})

        state["connected"] = True
        client.flush_deferred()

        assert sends == [
            ("dev1", "pk", "dk1", {"switch": True}),
            ("dev1", "pk", "dk1", {"speed": 5}),
        ]
        assert client._deferred_writes == []

    def test_flush_keeps_remaining_writes_when_connection_drops_mid_flush(self):
        """If a device is still down mid-flush, the unflushed tail stays queued."""
        sends = []
        client, state, parent_patch = self._make_client(sends, connected=False)
        with parent_patch:
            client.send_write("dev1", "pk", "dk1", {"switch": True})
            client.send_write("dev2", "pk", "dk2", {"switch": False})

        # Reconnect dk1 but leave dk2 down
        state["connected"] = True
        state["down_dks"].add("dk2")

        client.flush_deferred()

        assert sends == [("dev1", "pk", "dk1", {"switch": True})]
        assert len(client._deferred_writes) == 1
        assert client._deferred_writes[0][1:] == ("dev2", "pk", "dk2", {"switch": False})

    def test_flush_drops_expired_writes(self):
        """Writes queued longer than _WRITE_RETRY_WINDOW are dropped, not sent."""
        sends = []
        client, state, parent_patch = self._make_client(sends, connected=False)
        with parent_patch:
            client.send_write("dev1", "pk", "dk1", {"switch": True})

        # Simulate a long outage: age the queued write past the expiry window
        deadline, device_id, pk, dk, props = client._deferred_writes[0]
        client._deferred_writes[0] = (
            deadline - _WRITE_RETRY_WINDOW - 1,
            device_id,
            pk,
            dk,
            props,
        )

        state["connected"] = True
        client.flush_deferred()

        assert sends == []
        assert client._deferred_writes == []
