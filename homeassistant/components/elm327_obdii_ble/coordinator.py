"""Polling coordinator for the ELM327 OBD-II BLE integration.

Thin wrapper around :class:`elm327_obdii.Poller`. Uses
:class:`DataUpdateCoordinator` with a dynamic ``update_interval`` that
adjusts based on the polling state machine (5s when driving, 300s when
parked, 3600s when out of range). A bluetooth callback registered in
``__init__.py`` triggers an immediate refresh when the adapter
advertises, so polling resumes instantly when the device comes back in
range.
"""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import (
    BluetoothReachabilityIntent,
    async_address_present,
    async_address_reachability_diagnostics,
    async_ble_device_from_address,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
from .elm327_obdii import Poller, PollerConfig, PollingState, PollResult, ProfileConfig

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
            update_interval=timedelta(seconds=FAST_POLL_SECONDS),
        )
        self.entry = entry
        self._poller = Poller(self._build_poller_config(entry))
        self._last_state: PollingState = PollingState.OUT_OF_RANGE
        self._voltage: float | None = None
        self._was_unavailable: bool = True
        self.last_rediscovery_attempt: float = 0.0

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

    @property
    def address(self) -> str:
        """The BLE address of the adapter."""
        return str(self.entry.data[CONF_ADDRESS])

    def disconnect(self) -> None:
        """Close the BLE connection from an executor pool thread."""
        self._poller.disconnect()

    async def async_scan_supported_standard_pids(self) -> list[str]:
        """Live-scan the ECU for supported Mode 01 PIDs.

        Used by the options flow's standard-PID picker. Raises
        :class:`UpdateFailed` with a translation key if the adapter is
        out of range or cannot connect.
        """
        address = self.entry.data[CONF_ADDRESS]
        ble_device = async_ble_device_from_address(self.hass, address)
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
        try:
            return await self.hass.async_add_executor_job(
                self._poller.scan_supported_standard_pids
            )
        except RuntimeError:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connect_failed_scan"
            ) from None

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Run one polling cycle."""
        address = self.entry.data[CONF_ADDRESS]

        if not async_address_present(self.hass, address, connectable=True):
            self._update_interval_for(PollingState.OUT_OF_RANGE)
            if not self._was_unavailable:
                _LOGGER.warning("ELM327 adapter at %s is out of range", address)
                self._was_unavailable = True
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="device_out_of_range"
            )

        ble_device = async_ble_device_from_address(self.hass, address)
        if ble_device is None:
            reason = async_address_reachability_diagnostics(
                self.hass, address, BluetoothReachabilityIntent.CONNECTION
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": address, "reason": reason},
            )

        result: PollResult | None = await self.hass.async_add_executor_job(
            self._polled_cycle, ble_device
        )

        if result is None:
            if not self._was_unavailable:
                _LOGGER.warning("ELM327 adapter at %s became unavailable", address)
                self._was_unavailable = True
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="polling_failed"
            )

        if self._was_unavailable:
            _LOGGER.info("ELM327 adapter at %s is back online", address)
            self._was_unavailable = False

        self._last_state = result.state
        if result.voltage is not None:
            self._voltage = result.voltage

        _LOGGER.debug(
            "%s: Poll result — state=%s, voltage=%s, any_success=%s, data_keys=%s",
            address,
            result.state.value,
            result.voltage,
            result.any_success,
            list(result.data.keys()) if result.data else [],
        )

        self._update_interval_for(result.state)

        if not result.any_success and result.state in (
            PollingState.CAR_OFF,
            PollingState.GRACE_PERIOD,
        ):
            return self.data or {}
        return dict(result.data)

    def _update_interval_for(self, state: PollingState) -> None:
        """Map the polling state to the matching ``update_interval``."""
        if state == PollingState.CAR_OFF:
            self.update_interval = timedelta(seconds=SLOW_POLL_SECONDS)
        elif state == PollingState.OUT_OF_RANGE:
            self.update_interval = timedelta(seconds=OUT_OF_RANGE_POLL_SECONDS)
        else:
            self.update_interval = timedelta(seconds=FAST_POLL_SECONDS)

    def _connect(self, ble_dev: BLEDevice) -> bool:
        """Executor-thread helper: open the BLE connection if not already."""
        uuid_write = self.entry.data[CONF_UUID_WRITE]
        uuid_read = self.entry.data[CONF_UUID_READ]
        _LOGGER.debug(
            "%s: Connecting (uuid_write=%s, uuid_read=%s)",
            self.entry.data[CONF_ADDRESS],
            uuid_write,
            uuid_read,
        )
        connected = self._poller.connect(ble_dev, self.hass.loop, uuid_write, uuid_read)
        _LOGGER.debug("%s: Connect result=%s", self.entry.data[CONF_ADDRESS], connected)
        return connected

    def _polled_cycle(self, ble_dev: BLEDevice) -> PollResult | None:
        """Executor-thread helper: ensure connected, then run one poll."""
        if not self._poller.is_connected:
            if not self._connect(ble_dev):
                _LOGGER.debug(
                    "%s: Poll cycle skipped — connect failed",
                    self.entry.data[CONF_ADDRESS],
                )
                return None
        return self._poller.poll_once()
