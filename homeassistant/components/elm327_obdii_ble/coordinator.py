"""Polling coordinator for the ELM327 OBD-II BLE integration.

Thin wrapper around :class:`elm327_obdii.Poller`. The coordinator owns
the HA-specific concerns (``DataUpdateCoordinator`` lifecycle,
``async_address_present``, ``async_ble_device_from_address``,
``UpdateFailed`` translation keys, executor dispatch, dynamic
``update_interval``) and delegates the polling-domain state and
orchestration to the library's :class:`Poller` façade.
"""

from datetime import timedelta
import logging
import time
from typing import TYPE_CHECKING, Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    async_address_present,
    async_ble_device_from_address,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ATRV_SUPPORTED,
    CONF_FAST_POLL,
    CONF_GRACE_PERIOD,
    CONF_PROFILE,
    CONF_SLOW_POLL,
    CONF_UUID_READ,
    CONF_UUID_WRITE,
    CONF_VOLTAGE_CHECK,
    CONF_VOLTAGE_OFF,
    CONF_VOLTAGE_ON,
    CONF_XS_POLL,
    DEFAULT_FAST_POLL,
    DEFAULT_SLOW_POLL,
    DEFAULT_UUID_READ,
    DEFAULT_UUID_WRITE,
    DEFAULT_XS_POLL,
    DOMAIN,
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
    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)


class Elm327ObdiiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Drives the library :class:`Poller` from HA's polling scheduler."""

    def __init__(self, hass: HomeAssistant, entry: Elm327ObdiiConfigEntry) -> None:
        """Initialize the coordinator and build the Poller from the config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_FAST_POLL),
        )
        self.entry = entry
        self._poller = Poller(self._build_poller_config(entry))
        # Lock-free flag read by the event loop (binary_sensor platform).
        # Updated only from the executor thread (inside _async_update_data's
        # executor dispatch) and from disconnect(). Staleness can extend up
        # to slow_poll (300s) when the adapter goes out of range.
        self._ble_connected = False
        # Two separate debounce timestamps - one for poll-cycle connection
        # attempts, one for BLE re-discovery callback. Sharing a single
        # timestamp caused normal polls to suppress the rapid-refresh-on-
        # arrival logic (and vice versa).
        self.last_rediscovery_attempt: float = 0.0
        self._offline_since: float | None = None

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
    def ble_connected(self) -> bool:
        """True if the BLE link to the adapter is up."""
        return self._ble_connected

    @property
    def car_connected(self) -> bool:
        """True if the vehicle is in CAR_ON or GRACE_PERIOD state.

        GRACE_PERIOD counts as connected because the vehicle's ECU may
        still respond to queries during the brief voltage dip that
        triggers the grace window (e.g. during engine crank).
        """
        return self._ble_connected and self._poller.state in (
            PollingState.CAR_ON,
            PollingState.GRACE_PERIOD,
        )

    def disconnect(self) -> None:
        """Close the BLE connection from an executor pool thread."""
        self._poller.disconnect()
        self._ble_connected = False

    async def async_scan_supported_standard_pids(self) -> list[str]:
        """Live-scan the ECU for supported Mode 01 PIDs.

        Used by the options flow's standard-PID picker. Raises
        :class:`UpdateFailed` with a translation key if the adapter is
        out of range or cannot connect.
        """
        if not self._ble_connected:
            address = self.entry.data[CONF_ADDRESS]
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="adapter_out_of_range"
                )
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

    def _connect(self, ble_dev: BLEDevice) -> bool:
        """Executor-thread helper: open the BLE connection if not already."""
        uuid_write = self.entry.options.get(
            CONF_UUID_WRITE,
            self.entry.data.get(CONF_UUID_WRITE, DEFAULT_UUID_WRITE),
        )
        uuid_read = self.entry.options.get(
            CONF_UUID_READ,
            self.entry.data.get(CONF_UUID_READ, DEFAULT_UUID_READ),
        )
        ok = self._poller.connect(ble_dev, self.hass.loop, uuid_write, uuid_read)
        self._ble_connected = ok or self._poller.is_connected
        return ok

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic query trigger."""
        address = self.entry.data[CONF_ADDRESS]
        if not async_address_present(self.hass, address, connectable=True):
            if self._offline_since is None:
                self._offline_since = time.monotonic()
            if time.monotonic() - self._offline_since > 60:
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

        result: PollResult | None = await self.hass.async_add_executor_job(
            self._polled_cycle, ble_dev
        )

        if result is None:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="polling_failed"
            )

        self._update_interval_for(result.state)
        if not result.any_success and result.state == PollingState.CAR_OFF:
            # Engine off + nothing came back this cycle - surface as a
            # transient failure so HA marks entities unavailable rather
            # than showing stale data indefinitely.
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="polling_failed"
            )
        return dict(result.data)

    def _polled_cycle(self, ble_dev: BLEDevice) -> PollResult | None:
        """Executor-thread helper: ensure connected, then run one poll.

        Returns the :class:`PollResult`, or None if the connection
        attempt failed (the coordinator surfaces this as
        :class:`UpdateFailed`).
        """
        if not self._poller.is_connected:
            if not self._connect(ble_dev):
                return None
        try:
            return self._poller.poll_once()
        except BleakError, TimeoutError, OSError, ConnectionError, TransportError:
            self._ble_connected = self._poller.is_connected
            return None

    def _update_interval_for(self, state: PollingState) -> None:
        """Map the polling state to the matching ``update_interval``."""
        if state == PollingState.CAR_OFF:
            self.update_interval = timedelta(
                seconds=self.entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
            )
        elif state == PollingState.OUT_OF_RANGE:
            self.update_interval = timedelta(
                seconds=self.entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
            )
        else:
            # CAR_ON or GRACE_PERIOD - poll fast to catch transient
            # state changes and the next voltage dip.
            self.update_interval = timedelta(
                seconds=self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
            )
