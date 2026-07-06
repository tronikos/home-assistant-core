"""Polling coordinator for the ELM327 OBD-II BLE integration.

Thin wrapper around :class:`elm327_obdii.Poller`. Subclasses
:class:`ActiveBluetoothDataUpdateCoordinator` so HA handles
advertisement-driven availability tracking and poll debouncing; we
just supply ``needs_poll_method`` (when to poll) and ``poll_method``
(how to poll).
"""

import logging
from typing import TYPE_CHECKING, Any, override

from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_ATRV_SUPPORTED,
    CONF_GRACE_PERIOD,
    CONF_PROFILE,
    CONF_UUID_READ,
    CONF_UUID_WRITE,
    CONF_VOLTAGE_CHECK,
    CONF_VOLTAGE_OFF,
    CONF_VOLTAGE_ON,
    DOMAIN,
    FAST_POLL_SECONDS,
    OUT_OF_RANGE_POLL_SECONDS,
    SLOW_POLL_SECONDS,
)
from .elm327_obdii import (
    Poller,
    PollerConfig,
    PollingState,
    PollResult,
    ProfileConfig,
    TransportError,
)

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)


class Elm327ObdiiCoordinator(ActiveBluetoothDataUpdateCoordinator[dict[str, Any]]):
    """Drives the library :class:`Poller` from BLE advertisement events."""

    def __init__(self, hass: HomeAssistant, entry: Elm327ObdiiConfigEntry) -> None:
        """Initialize the coordinator and build the Poller from the config entry."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=entry.data[CONF_ADDRESS],
            mode=BluetoothScanningMode.ACTIVE,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            connectable=True,
        )
        self.entry = entry
        self._poller = Poller(self._build_poller_config(entry))
        self._last_state: PollingState = PollingState.OUT_OF_RANGE
        self._voltage: float | None = None
        self._ble_device: BLEDevice | None = None
        self._was_unavailable: bool = True

    @staticmethod
    def _build_poller_config(entry: Elm327ObdiiConfigEntry) -> PollerConfig:
        """Map a config entry's data + options to a :class:`PollerConfig`."""
        opts = entry.options
        data = entry.data
        return PollerConfig(
            profile=ProfileConfig.from_dict(opts[CONF_PROFILE]),
            atrv_supported=data[CONF_ATRV_SUPPORTED],
            voltage_check_enabled=opts[CONF_VOLTAGE_CHECK],
            voltage_on=opts[CONF_VOLTAGE_ON],
            voltage_off=opts[CONF_VOLTAGE_OFF],
            grace_seconds=opts[CONF_GRACE_PERIOD],
        )

    @property
    def polling_state(self) -> PollingState:
        """Last known vehicle polling state."""
        return self._last_state

    @property
    def voltage(self) -> float | None:
        """Last measured 12V battery voltage (from AT RV), or None."""
        return self._voltage

    def disconnect(self) -> None:
        """Close the BLE connection from an executor pool thread."""
        self._poller.disconnect()

    async def async_scan_supported_standard_pids(self) -> list[str]:
        """Live-scan the ECU for supported Mode 01 PIDs.

        Used by the options flow's standard-PID picker. Raises
        :class:`UpdateFailed` with a translation key if the adapter is
        out of range or cannot connect.
        """
        ble_device = self._ble_device or async_ble_device_from_address(
            self.hass, self.address.upper(), True
        )
        if ble_device is None:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="adapter_out_of_range"
            )
        if not self._poller.is_connected:
            connected = await self.hass.async_add_executor_job(
                self._connect, ble_device
            )
            if not connected:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="connect_failed_scan"
                )
        return await self.hass.async_add_executor_job(
            self._poller.scan_supported_standard_pids
        )

    @callback
    def _needs_poll(
        self,
        service_info: BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        """Return True if a poll is needed based on the polling state machine."""
        return (
            self.hass.state is CoreState.running
            and (
                seconds_since_last_poll is None
                or seconds_since_last_poll >= self._interval_for_state(self._last_state)
            )
            and bool(
                async_ble_device_from_address(
                    self.hass, service_info.device.address.upper(), connectable=True
                )
            )
        )

    @staticmethod
    def _interval_for_state(state: PollingState) -> float:
        """Map a polling state to its poll interval in seconds."""
        if state == PollingState.CAR_OFF:
            return SLOW_POLL_SECONDS
        if state == PollingState.OUT_OF_RANGE:
            return OUT_OF_RANGE_POLL_SECONDS
        return FAST_POLL_SECONDS

    @callback
    @override
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Keep the freshest BLEDevice reference for connection attempts."""
        self._ble_device = service_info.device
        super()._async_handle_bluetooth_event(service_info, change)

    @callback
    @override
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Device hasn't advertised in 5 minutes — force state to OUT_OF_RANGE."""
        self._last_state = PollingState.OUT_OF_RANGE
        # Poller.disconnect() closes the BleakClient synchronously and may
        # block on the executor thread; never call it from the event loop.
        self.hass.async_add_executor_job(self._poller.disconnect)
        super()._async_handle_unavailable(service_info)

    async def _async_update(
        self, service_info: BluetoothServiceInfoBleak
    ) -> dict[str, Any]:
        """Run one polling cycle on the executor pool."""
        ble_device = service_info.device
        result: PollResult | None = await self.hass.async_add_executor_job(
            self._polled_cycle, ble_device
        )
        if result is None:
            if not self._was_unavailable:
                _LOGGER.warning("ELM327 adapter at %s became unavailable", self.address)
                self._was_unavailable = True
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="polling_failed"
            )
        if self._was_unavailable:
            _LOGGER.info("ELM327 adapter at %s is back online", self.address)
            self._was_unavailable = False
        self._last_state = result.state
        self._voltage = result.voltage
        # Car off is a routine state, not a failure — return cached data
        # so sensors hold their last known values and last_poll_successful
        # stays True (distinguishing "parked" from "actually broken").
        if not result.any_success and result.state == PollingState.CAR_OFF:
            return self.data or {}
        return dict(result.data)

    def _connect(self, ble_dev: BLEDevice) -> bool:
        """Executor-thread helper: open the BLE connection if not already."""
        uuid_write = self.entry.data[CONF_UUID_WRITE]
        uuid_read = self.entry.data[CONF_UUID_READ]
        return self._poller.connect(ble_dev, self.hass.loop, uuid_write, uuid_read)

    def _polled_cycle(self, ble_dev: BLEDevice) -> PollResult | None:
        """Executor-thread helper: ensure connected, then run one poll."""
        if not self._poller.is_connected:
            if not self._connect(ble_dev):
                return None
        try:
            return self._poller.poll_once()
        except BleakError, TimeoutError, OSError, ConnectionError, TransportError:
            return None
