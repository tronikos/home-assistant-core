"""Config flow for Universal OBD BLE."""

import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import ClientTimeout
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from obdii import Command, Connection, Mode, Response
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict

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
    DEFAULT_GRACE_PERIOD,
    DEFAULT_SLOW_POLL,
    DEFAULT_UUID_READ,
    DEFAULT_UUID_WRITE,
    DEFAULT_VOLTAGE_OFF,
    DEFAULT_VOLTAGE_ON,
    DEFAULT_XS_POLL,
    DOMAIN,
)
from .obdii.transport_ble import TransportBLE

_LOGGER = logging.getLogger(__name__)


def get_fallback_profiles() -> list[dict]:
    """Helper to load offline fallback profiles."""
    try:
        path = Path(__file__).parent / "wican" / "fallback_profiles.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Failed to load fallback profiles: %s", err)
        return []


class UniversalObdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the setup config flow step-by-step."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize parameters."""
        self._address: str | None = None
        self._title: str = "Universal OBD BLE"
        self.profiles: dict[str, Any] = {}
        self.selected_profile_json: str | dict[str, Any] | None = None
        self.atrv_supported: bool = True
        self._uuid_read: str = DEFAULT_UUID_READ
        self._uuid_write: str = DEFAULT_UUID_WRITE
        self._discovered_characteristics: list[BleakGATTCharacteristic] = []

    def _test_connection_sync(
        self, ble_device, uuid_write=None, uuid_read=None
    ) -> bool | None:
        """Thread-safe connection test executed in the executor pool."""
        resp: Response | None = None
        try:
            transport = TransportBLE(
                ble_device=ble_device,
                loop=self.hass.loop,
                uuid_write=uuid_write or DEFAULT_UUID_WRITE,
                uuid_read=uuid_read or DEFAULT_UUID_READ,
                timeout=5.0,
            )
            conn = Connection(transport)

            # Fetch resolved UUIDs from transport if auto-discovered
            self._uuid_write = transport.config.get("uuid_write", self._uuid_write)
            self._uuid_read = transport.config.get("uuid_read", self._uuid_read)

            resp = conn.query(Command(Mode.AT, "RV"))
            conn.close()
        except Exception as e:  # noqa: BLE001
            _LOGGER.debug("Connection test failed: %s", e)
            return None
        else:
            return resp is not None and b"?" not in resp.raw

    async def _async_get_characteristics(
        self, ble_device
    ) -> list[BleakGATTCharacteristic]:
        """Get characteristics quickly via pure BLE service cache."""
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                ble_device.name or "Unknown Device",
                max_attempts=2,
            )
            characteristics = []
            for service in client.services:
                characteristics.extend(service.characteristics)
            await client.disconnect()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to fetch pure GATT characteristics: %s", err)
            return []
        else:
            return characteristics

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = discovery_info.name or discovery_info.address

        ble_device = discovery_info.device
        res = await self.hass.async_add_executor_job(
            self._test_connection_sync, ble_device
        )
        if res is None:
            self._discovered_characteristics = await self._async_get_characteristics(
                ble_device
            )
            return await self.async_step_connection()

        self.atrv_supported = res
        return await self.async_step_profile()

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Standard user setup step."""
        errors = {}
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            assert self._address is not None
            ble_device = async_ble_device_from_address(self.hass, self._address, True)
            if not ble_device:
                errors["base"] = "device_not_found"
            else:
                self._title = ble_device.name or self._address
                res = await self.hass.async_add_executor_job(
                    self._test_connection_sync, ble_device
                )
                if res is None:
                    self._discovered_characteristics = (
                        await self._async_get_characteristics(ble_device)
                    )
                    return await self.async_step_connection()

                self.atrv_supported = res
                return await self.async_step_profile()

        devices = {
            dev.address: f"{dev.name or 'Unknown'} ({dev.address})"
            for dev in async_discovered_service_info(self.hass)
        }
        if not devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(devices)}),
            errors=errors,
        )

    async def async_step_connection(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual connection setup when auto-discovery fails."""
        if user_input is not None:
            self._uuid_write = user_input[CONF_UUID_WRITE]
            self._uuid_read = user_input[CONF_UUID_READ]

            address = self._address
            assert address is not None
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device:
                res = await self.hass.async_add_executor_job(
                    self._test_connection_sync,
                    ble_device,
                    self._uuid_write,
                    self._uuid_read,
                )
                self.atrv_supported = bool(res)

            return await self.async_step_profile()

        if not self._discovered_characteristics:
            return self.async_abort(reason="no_characteristics_found")

        options: list[SelectOptionDict] = [
            SelectOptionDict(
                value=char.uuid,
                label=f"{char.description} ({char.uuid.split('-')[0]})",
            )
            for char in self._discovered_characteristics
        ]

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UUID_READ, default=self._uuid_read
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_UUID_WRITE, default=self._uuid_write
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_profile(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Profile Selection."""
        if not self.profiles:
            fallback = get_fallback_profiles()
            self.profiles = {car["car_model"]: car for car in fallback}
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    "https://raw.githubusercontent.com/meatpiHQ/wican-fw/refs/heads/main/vehicle_profiles.json",
                    timeout=ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if (
                            isinstance(data, dict)
                            and "cars" in data
                            and isinstance(data["cars"], list)
                        ):
                            self.profiles = {
                                car["car_model"]: car for car in data["cars"]
                            }
                    else:
                        _LOGGER.warning(
                            "Could not download vehicle profiles, status: %s",
                            resp.status,
                        )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not download vehicle profiles, falling back: %s", err
                )

        if user_input is not None:
            car = self.profiles[user_input["car"]]
            self.selected_profile_json = json.dumps(car, indent=2)
            return await self.async_step_editor()

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {vol.Required("car"): vol.In(list(self.profiles.keys()))}
            ),
        )

    async def async_step_editor(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """JSON Profile Editor."""
        errors = {}
        if user_input is not None:
            try:
                profile_data = json.loads(user_input[CONF_PROFILE])
                self.selected_profile_json = profile_data
                return await self.async_step_polling()
            except json.JSONDecodeError:
                errors["base"] = "invalid_json"
                self.selected_profile_json = user_input[CONF_PROFILE]

        return self.async_show_form(
            step_id="editor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROFILE, default=self.selected_profile_json
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_polling(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Polling & Battery Protection Config."""
        if user_input is not None:
            voltage_check_bool = user_input[CONF_VOLTAGE_CHECK] == "AT RV"
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_ADDRESS: self._address,
                    CONF_ATRV_SUPPORTED: self.atrv_supported,
                    CONF_UUID_READ: self._uuid_read,
                    CONF_UUID_WRITE: self._uuid_write,
                },
                options={
                    CONF_PROFILE: json.dumps(self.selected_profile_json),
                    CONF_VOLTAGE_CHECK: voltage_check_bool,
                    CONF_FAST_POLL: user_input[CONF_FAST_POLL],
                    CONF_SLOW_POLL: user_input[CONF_SLOW_POLL],
                    CONF_XS_POLL: user_input[CONF_XS_POLL],
                    CONF_VOLTAGE_ON: user_input[CONF_VOLTAGE_ON],
                    CONF_VOLTAGE_OFF: user_input[CONF_VOLTAGE_OFF],
                    CONF_GRACE_PERIOD: user_input[CONF_GRACE_PERIOD],
                },
            )

        return self.async_show_form(
            step_id="polling",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOLTAGE_CHECK,
                        default="AT RV" if self.atrv_supported else "Disabled",
                    ): vol.In(["AT RV", "Disabled"]),
                    vol.Required(CONF_FAST_POLL, default=DEFAULT_FAST_POLL): int,
                    vol.Required(CONF_SLOW_POLL, default=DEFAULT_SLOW_POLL): int,
                    vol.Required(CONF_XS_POLL, default=DEFAULT_XS_POLL): int,
                    vol.Required(CONF_VOLTAGE_ON, default=DEFAULT_VOLTAGE_ON): float,
                    vol.Required(CONF_VOLTAGE_OFF, default=DEFAULT_VOLTAGE_OFF): float,
                    vol.Required(CONF_GRACE_PERIOD, default=DEFAULT_GRACE_PERIOD): int,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return UniversalObdBleOptionsFlow()


class UniversalObdBleOptionsFlow(config_entries.OptionsFlow):
    """Handle options adjustment post-setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage option values."""
        errors = {}
        if user_input is not None:
            try:
                # Verify JSON is loadable
                json.loads(user_input[CONF_PROFILE])
                voltage_check_bool = user_input[CONF_VOLTAGE_CHECK] == "AT RV"

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_PROFILE: user_input[CONF_PROFILE],
                        CONF_VOLTAGE_CHECK: voltage_check_bool,
                        CONF_UUID_READ: user_input[CONF_UUID_READ],
                        CONF_UUID_WRITE: user_input[CONF_UUID_WRITE],
                        CONF_FAST_POLL: user_input[CONF_FAST_POLL],
                        CONF_SLOW_POLL: user_input[CONF_SLOW_POLL],
                        CONF_XS_POLL: user_input[CONF_XS_POLL],
                        CONF_VOLTAGE_ON: user_input[CONF_VOLTAGE_ON],
                        CONF_VOLTAGE_OFF: user_input[CONF_VOLTAGE_OFF],
                        CONF_GRACE_PERIOD: user_input[CONF_GRACE_PERIOD],
                    },
                )
            except json.JSONDecodeError:
                errors["base"] = "invalid_json"

        profile_json = self.config_entry.options.get(CONF_PROFILE, "{}")
        voltage_check = self.config_entry.options.get(CONF_VOLTAGE_CHECK, True)
        uuid_read = self.config_entry.options.get(
            CONF_UUID_READ,
            self.config_entry.data.get(CONF_UUID_READ, DEFAULT_UUID_READ),
        )
        uuid_write = self.config_entry.options.get(
            CONF_UUID_WRITE,
            self.config_entry.data.get(CONF_UUID_WRITE, DEFAULT_UUID_WRITE),
        )
        fast_poll = self.config_entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
        slow_poll = self.config_entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
        xs_poll = self.config_entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
        on_threshold = self.config_entry.options.get(
            CONF_VOLTAGE_ON, DEFAULT_VOLTAGE_ON
        )
        off_threshold = self.config_entry.options.get(
            CONF_VOLTAGE_OFF, DEFAULT_VOLTAGE_OFF
        )
        grace_period = self.config_entry.options.get(
            CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROFILE, default=profile_json
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Required(
                        CONF_VOLTAGE_CHECK,
                        default="AT RV" if voltage_check else "Disabled",
                    ): vol.In(["AT RV", "Disabled"]),
                    vol.Required(CONF_UUID_READ, default=uuid_read): str,
                    vol.Required(CONF_UUID_WRITE, default=uuid_write): str,
                    vol.Required(CONF_FAST_POLL, default=fast_poll): int,
                    vol.Required(CONF_SLOW_POLL, default=slow_poll): int,
                    vol.Required(CONF_XS_POLL, default=xs_poll): int,
                    vol.Required(CONF_VOLTAGE_ON, default=on_threshold): float,
                    vol.Required(CONF_VOLTAGE_OFF, default=off_threshold): float,
                    vol.Required(CONF_GRACE_PERIOD, default=grace_period): int,
                }
            ),
            errors=errors,
        )
