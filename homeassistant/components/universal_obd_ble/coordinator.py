"""Polling coordinator for Universal OBD BLE."""

import contextlib
from datetime import timedelta
import logging
import threading
import time
from typing import Any

from bleak.backends.device import BLEDevice
from obdii import Connection

from homeassistant.components.bluetooth import (
    async_address_present,
    async_ble_device_from_address,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import UniversalObdConfigEntry
from .const import (
    CONF_ATRV_SUPPORTED,
    CONF_FAST_POLL,
    CONF_GRACE_PERIOD,
    CONF_SLOW_POLL,
    CONF_UOPS,
    CONF_UUID_READ,
    CONF_UUID_WRITE,
    CONF_VOLTAGE_CHECK,
    CONF_VOLTAGE_OFF,
    CONF_VOLTAGE_ON,
    CONF_XS_POLL,
    DEFAULT_FAST_POLL,
    DEFAULT_GRACE_PERIOD,
    DEFAULT_SLOW_POLL,
    DEFAULT_UUID_READ,
    DEFAULT_UUID_WRITE,
    DEFAULT_VOLTAGE_OFF,
    DEFAULT_VOLTAGE_ON,
    DEFAULT_XS_POLL,
    DOMAIN,
)
from .uops import (
    CanContext,
    PollingState,
    QueryItem,
    UopsConfig,
    build_query_plan_from_uops,
    check_voltage,
    create_connection,
    run_query_plan,
    scan_supported_pids,
)

_LOGGER = logging.getLogger(__name__)


class UniversalObdCoordinator(DataUpdateCoordinator):
    """Local data coordinator that runs a pre-built UOPS query plan."""

    def __init__(self, hass: HomeAssistant, entry: UniversalObdConfigEntry) -> None:
        """Initialize coordinator state machine."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5)
        )
        self.entry = entry
        self.data: dict[str, Any] = {}
        self.state = PollingState.OUT_OF_RANGE
        self.grace_start: float | None = None
        self.api: Connection | None = None
        self._current_context: CanContext | None = None
        self.consecutive_failures = 0
        self.last_successful_poll: float | None = None
        self.last_discovery_attempt: float = 0.0
        self._offline_since: float | None = None

        uops = UopsConfig.from_dict(self.entry.options.get(CONF_UOPS, {}))
        self._query_plan = build_query_plan_from_uops(uops)

        self._lock = threading.Lock()

    @property
    def ble_connected(self) -> bool:
        """True if the BLE link to the adapter is up."""
        with self._lock:
            return self.api.is_connected() if self.api else False

    @property
    def car_connected(self) -> bool:
        """True if the vehicle responded recently."""
        if not self.ble_connected or self.last_successful_poll is None:
            return False
        fast_poll: int = self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
        return bool(
            (time.monotonic() - self.last_successful_poll) < (fast_poll * 2.5 + 5)
        )

    def disconnect(self) -> None:
        """Safely close the connection from an executor pool thread."""
        with self._lock:
            if self.api:
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None
                self._current_context = None

    async def async_scan_supported_standard_pids(self) -> list[str]:
        """Live-scan the ECU for supported Mode 01 PIDs."""
        if not self.ble_connected:
            address = self.entry.data[CONF_ADDRESS]
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="adapter_out_of_range"
                )
            connected = await self.hass.async_add_executor_job(
                self._ensure_connected, ble_device
            )
            if not connected:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="connect_failed_scan"
                )

        return await self.hass.async_add_executor_job(self._sync_scan_supported_pids)

    def _sync_scan_supported_pids(self) -> list[str]:
        """Run the bitmap walk holding the API lock."""
        with self._lock:
            if not self.api or not self.api.is_connected():
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="adapter_not_connected_scan",
                )
            return scan_supported_pids(self.api)

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic query trigger."""
        address = self.entry.data[CONF_ADDRESS]
        if not async_address_present(self.hass, address, connectable=True):
            if self._offline_since is None:
                self._offline_since = time.monotonic()
            if time.monotonic() - self._offline_since > 60:
                self.state = PollingState.OUT_OF_RANGE
                self.update_interval = timedelta(
                    seconds=self.entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
                )
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="device_out_of_range"
            )

        self._offline_since = None

        ble_dev = async_ble_device_from_address(self.hass, address, True)
        if ble_dev is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": address},
            )

        plan = list(self._query_plan)

        result = await self.hass.async_add_executor_job(
            self._sync_update, ble_dev, plan
        )

        if result.get("failed"):
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="polling_failed"
            )

        self.state = result["state"]
        self.update_interval = result["update_interval"]
        self.data = result["data"]
        return self.data

    def _sync_update(
        self,
        ble_dev: BLEDevice,
        plan: list[tuple[CanContext, list[QueryItem]]],
    ) -> dict[str, Any]:
        """Thread-safe update cycle executed inside the executor pool."""
        with self._lock:
            res_state = self.state
            res_interval = self.update_interval
            res_data: dict[str, Any] = dict(self.data)

            if not self._ensure_connected(ble_dev):
                self.consecutive_failures += 1
                return {"failed": True, "error": "Connection to OBD adapter failed"}

            assert self.api is not None

            try:
                fast_interval = timedelta(
                    seconds=self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
                )

                res_state, res_interval, self.grace_start = self._handle_voltage_check(
                    fast_interval
                )

                if res_state != PollingState.CAR_OFF:
                    data, any_success, self._current_context = run_query_plan(
                        self.api, plan, self._current_context
                    )
                    res_data.update(data)
                    if any_success:
                        self.last_successful_poll = time.monotonic()

                self.consecutive_failures = 0

            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Error during polling cycle, resetting connection: %s", e
                )
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None
                self._current_context = None
                self.consecutive_failures += 1
                return {"failed": True, "error": str(e)}

            return {
                "data": res_data,
                "state": res_state,
                "update_interval": res_interval,
                "failed": False,
            }

    def _handle_voltage_check(
        self, fast_interval: timedelta
    ) -> tuple[str, timedelta, float | None]:
        """Query battery voltage and determine the polling state + interval."""
        assert self.api is not None
        state, interval, grace = check_voltage(
            api=self.api,
            atrv_supported=self.entry.data.get(CONF_ATRV_SUPPORTED, True),
            voltage_check_enabled=self.entry.options.get(CONF_VOLTAGE_CHECK, True),
            on_threshold=self.entry.options.get(CONF_VOLTAGE_ON, DEFAULT_VOLTAGE_ON),
            off_threshold=self.entry.options.get(CONF_VOLTAGE_OFF, DEFAULT_VOLTAGE_OFF),
            grace_seconds=self.entry.options.get(
                CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD
            ),
            current_state=self.state,
            grace_start=self.grace_start,
        )
        if interval is None:
            if state == PollingState.CAR_OFF:
                interval = timedelta(
                    seconds=self.entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
                )
            else:
                interval = fast_interval
        return state, interval, grace

    def _ensure_connected(self, ble_dev: BLEDevice) -> bool:
        """Ensure the BLE OBD-II adapter connection is active."""
        if self.api and self.api.is_connected():
            return True

        self.last_discovery_attempt = time.monotonic()

        if self.api:
            with contextlib.suppress(Exception):
                self.api.close()
            self.api = None
            self._current_context = None

        uuid_write = self.entry.options.get(
            CONF_UUID_WRITE,
            self.entry.data.get(CONF_UUID_WRITE, DEFAULT_UUID_WRITE),
        )
        uuid_read = self.entry.options.get(
            CONF_UUID_READ,
            self.entry.data.get(CONF_UUID_READ, DEFAULT_UUID_READ),
        )
        self.api = create_connection(ble_dev, self.hass.loop, uuid_write, uuid_read)
        if self.api is None:
            return False
        self._current_context = None
        return True
