"""Bluetooth Low Energy transport for OBDII."""

import asyncio
from collections.abc import Coroutine
import contextlib
import logging
from threading import Event, Lock
from time import monotonic
from typing import Any, Self

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from obdii.basetypes import MISSING
from obdii.transports.transport_base import TransportBase

_LOGGER: logging.Logger = logging.getLogger(__package__)


class TransportBLE(TransportBase):
    """Bluetooth Low Energy transport implementation."""

    def __init__(
        self,
        ble_device: BLEDevice = MISSING,
        uuid_write: str = MISSING,
        uuid_read: str = MISSING,
        timeout: float = 10.0,
        loop: asyncio.AbstractEventLoop | None = None,
        **kwargs,
    ) -> None:
        """Initialize the BLE transport."""
        if ble_device is MISSING or uuid_write is MISSING or uuid_read is MISSING:
            raise ValueError(
                f"ble_device ({ble_device}), uuid_write ({uuid_write}) and uuid_read ({uuid_read}) must be specified for TransportBLE."
            )

        self.config: dict[str, Any] = {
            "uuid_write": uuid_write,
            "uuid_read": uuid_read,
            "timeout": timeout,
            **kwargs,
        }

        self._ble_device = ble_device
        self._ble_conn: BleakClient | None = None
        self._buffer = bytearray()
        self._lock = Lock()
        self._data_ready = Event()
        self._loop = loop

    def __repr__(self) -> str:
        """Return representation of TransportBLE."""
        return f"<TransportBLE {self._ble_device}>"

    def _run_coro(self, coro: Coroutine) -> Any:
        """Run a coroutine thread-safely in the specified loop."""
        if self._loop is None:
            raise RuntimeError("Event loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.config["timeout"])

    def _notify_callback(self, _, data: bytearray) -> None:
        """Handle incoming notify notifications from BLE device."""
        with self._lock:
            self._buffer.extend(data)
        self._data_ready.set()

    async def async_connect(self) -> None:
        """Establish BLE connection and enable notify descriptors.

        Tries the configured UUIDs first, then falls back to dynamic GATT
        service discovery so adapters with non-standard characteristic UUIDs
        still work without manual configuration.
        """
        _LOGGER.debug(
            "Attempting to connect to BLE device %s (%s)",
            self._ble_device.name,
            self._ble_device.address,
        )
        self._ble_conn = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device,
            self._ble_device.name or "Unknown Device",
            max_attempts=3,
        )

        services = self._ble_conn.services
        write_char: str | None = None
        read_char: str | None = None

        # 1. Try the configured UUIDs first (exact match, case-insensitive).
        for service in services:
            for char in service.characteristics:
                if char.uuid.lower() == self.config.get("uuid_write", "").lower():
                    write_char = char.uuid
                if char.uuid.lower() == self.config.get("uuid_read", "").lower():
                    read_char = char.uuid

        # 2. Dynamic discovery fallback for adapters with non-standard UUIDs.
        if not write_char or not read_char:
            _LOGGER.debug(
                "Configured characteristics not found - attempting dynamic discovery"
            )
            for service in services:
                # Skip standard BLE SIG services (0x1800-0x18xx) to avoid
                # accidentally claiming Generic Access or Device Information chars.
                if service.uuid.lower().startswith("000018"):
                    continue
                for char in service.characteristics:
                    props = char.properties
                    if not write_char and (
                        "write" in props or "write-without-response" in props
                    ):
                        write_char = char.uuid
                        _LOGGER.debug(
                            "Auto-discovered write characteristic: %s", write_char
                        )
                    if not read_char and ("notify" in props or "indicate" in props):
                        read_char = char.uuid
                        _LOGGER.debug(
                            "Auto-discovered read characteristic: %s", read_char
                        )

        if not write_char or not read_char:
            raise RuntimeError(
                "Could not locate compatible Read/Write GATT characteristics. "
                "Verify the adapter UUIDs or try a different BLE serial profile."
            )

        # Persist discovered UUIDs so subsequent connect() calls skip re-discovery.
        self.config["uuid_write"] = write_char
        self.config["uuid_read"] = read_char

        await self._ble_conn.start_notify(
            self.config["uuid_read"], self._notify_callback
        )

    async def async_close(self) -> None:
        """Gracefully disconnect from BLE peripheral."""
        if self._ble_conn:
            try:
                if self._ble_conn.is_connected:
                    with contextlib.suppress(Exception):
                        await self._ble_conn.stop_notify(self.config["uuid_read"])
                    await self._ble_conn.disconnect()
            finally:
                # Clear the reference in finally so is_connected() always returns
                # False after async_close(), even if disconnect() raised.
                self._ble_conn = None

    async def _write(self, query: bytes) -> None:
        """Write query bytes to GATT character representation."""
        if self._ble_conn is None:
            raise RuntimeError("BLE connection is not established.")
        await self._ble_conn.write_gatt_char(self.config["uuid_write"], query)

    def get_service_collection(self) -> BleakGATTServiceCollection:
        """Return discovered GATT service collection."""
        if self._ble_conn is None:
            raise RuntimeError("BLE connection is not established.")
        return self._ble_conn.services

    def connect(self, loop: asyncio.AbstractEventLoop | None = None, **kwargs) -> None:
        """Connect to BLE device blocking-wise."""
        self.config.update(kwargs)

        if loop is not None:
            self._loop = loop

        try:
            self._run_coro(self.async_connect())
        except Exception:
            self.close()  # Cleanup on failure
            raise

    def close(self) -> None:
        """Disconnect from BLE transport."""
        if self.is_connected():
            with contextlib.suppress(Exception):
                self._run_coro(self.async_close())
        # Wake up any reader threads currently blocked in read_bytes.
        self._data_ready.set()

    def is_connected(self) -> bool:
        """Verify GATT connection status."""
        if self._ble_conn is None:
            return False
        return self._ble_conn.is_connected

    def write_bytes(self, query: bytes) -> None:
        """Write raw bytes to target write characteristic."""
        if not self.is_connected():
            raise RuntimeError("BLE is not connected.")
        with self._lock:
            self._buffer.clear()
        self._data_ready.clear()
        self._run_coro(self._write(query))

    def read_bytes(self, expected_seq: bytes = b">", size: int = MISSING) -> bytes:
        """Read bytes until the terminal sequence or size limit is satisfied.

        Consuming (deleting) matched bytes from the internal buffer prevents
        stale data from a previous AT init response bleeding into the next
        query when back-to-back commands arrive faster than write_bytes can
        issue its buffer-clear.
        """
        lenterm = len(expected_seq)
        deadline = monotonic() + self.config["timeout"]

        while True:
            if not self.is_connected():
                raise RuntimeError("BLE connection lost while reading.")

            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("read timed out.")

            with self._lock:
                snapshot = bytes(self._buffer)

            consumed_len: int | None = None

            # Check for the terminal sequence anywhere in the buffer (not just
            # at the end) so a prompt that arrives mid-chunk is caught promptly.
            idx = snapshot.find(expected_seq)
            if idx != -1:
                consumed_len = idx + lenterm
            elif size is not MISSING and len(snapshot) >= size:
                consumed_len = size

            if consumed_len is not None:
                with self._lock:
                    ret_bytes = bytes(self._buffer[:consumed_len])
                    del self._buffer[:consumed_len]
                return ret_bytes

            self._data_ready.wait(timeout=remaining)
            self._data_ready.clear()

    def __enter__(self) -> Self:
        """Enter context manager block."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager block."""
        self.close()

    async def __aenter__(self) -> Self:
        """Enter async context manager block."""
        await self.async_connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager block."""
        await self.async_close()
