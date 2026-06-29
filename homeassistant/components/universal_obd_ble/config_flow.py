"""Config flow for Universal OBD BLE."""

import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import ClientTimeout
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from obdii import Command, Connection, Mode, Response, commands as veh_commands
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import CONF_ADDRESS, CONF_COMMAND, CONF_DEVICE_CLASS, CONF_ICON
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict

from .const import (
    CONF_ATRV_SUPPORTED,
    CONF_COMMANDS,
    CONF_FAST_POLL,
    CONF_GRACE_PERIOD,
    CONF_PROFILE,
    CONF_SLOW_POLL,
    CONF_STATE_CLASS,
    CONF_UNIT,
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
from .sensor import (
    get_list_of_units,
    propose_icon_from_command,
    propose_sensor_device_class,
    propose_sensor_state_class,
)

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
        self._selected_commands: list[Command] = []
        self._configured_commands: list[dict[str, str | None]] = []
        self._command: Command | None = None

    def _test_connection_sync(
        self, ble_device, uuid_write=None, uuid_read=None
    ) -> tuple[bool | None, str, str]:
        """Thread-safe connection test executed in the executor pool."""
        resp: Response | None = None
        conn = None
        final_write = uuid_write or DEFAULT_UUID_WRITE
        final_read = uuid_read or DEFAULT_UUID_READ

        try:
            transport = TransportBLE(
                ble_device=ble_device,
                loop=self.hass.loop,
                uuid_write=final_write,
                uuid_read=final_read,
                timeout=5.0,
            )
            conn = Connection(transport)

            # Capture discovered UUIDs without mutating flow state from the executor
            final_write = transport.config.get("uuid_write", final_write)
            final_read = transport.config.get("uuid_read", final_read)

            resp = conn.query(Command(Mode.AT, "RV"))
        except Exception as e:  # noqa: BLE001
            _LOGGER.debug("Connection test failed: %s", e)
            return None, final_write, final_read
        finally:
            # Ensure teardown happens safely even if queries fail
            if conn:
                with contextlib.suppress(Exception):
                    conn.close()

        success = resp is not None and b"?" not in resp.raw
        return success, final_write, final_read

    async def _async_get_characteristics(
        self, ble_device
    ) -> list[BleakGATTCharacteristic]:
        """Get characteristics quickly via pure BLE service cache."""
        client = None
        characteristics: list[BleakGATTCharacteristic] = []
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                ble_device.name or "Unknown Device",
                max_attempts=2,
            )
            for service in client.services:
                characteristics.extend(service.characteristics)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to fetch pure GATT characteristics: %s", err)
            return []
        else:
            return characteristics
        finally:
            # Use try/finally to prevent resource leaks on exceptions
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.disconnect()

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
        success, final_write, final_read = res

        # Apply captured UUIDs to flow state on the main thread
        self._uuid_write = final_write
        self._uuid_read = final_read

        if success is None:
            self._discovered_characteristics = await self._async_get_characteristics(
                ble_device
            )
            return await self.async_step_connection()

        self.atrv_supported = success
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
                success, final_write, final_read = res

                self._uuid_write = final_write
                self._uuid_read = final_read

                if success is None:
                    self._discovered_characteristics = (
                        await self._async_get_characteristics(ble_device)
                    )
                    return await self.async_step_connection()

                self.atrv_supported = success
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
                success, final_write, final_read = res
                self.atrv_supported = bool(success)
                self._uuid_write = final_write
                self._uuid_read = final_read

            return await self.async_step_profile()

        if not self._discovered_characteristics:
            return self.async_abort(reason="no_characteristics_found")

        # Fallback for missing characteristic descriptions
        options: list[SelectOptionDict] = [
            {
                "value": char.uuid,
                "label": f"{char.description or 'Unknown Characteristic'} ({char.uuid.split('-')[0]})",
            }
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
            # Offload blocking file system reads to the executor pool
            fallback = await self.hass.async_add_executor_job(get_fallback_profiles)
            self.profiles = {car["car_model"]: car for car in fallback}
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    "https://raw.githubusercontent.com/meatpiHQ/wican-fw/refs/heads/main/vehicle_profiles.json",
                    timeout=ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        # Allow parsing text/plain MIME types safely
                        data = await resp.json(content_type=None)
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
            car_model = user_input["car"]
            if car_model == "none":
                self.selected_profile_json = "{}"
                return await self.async_step_standard_commands_select()

            car = self.profiles[car_model]
            self.selected_profile_json = json.dumps(car, indent=2)
            return await self.async_step_editor()

        options = {
            "none": "None / Standard OBD-II Only",
            **{k: k for k in self.profiles},
        }

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {vol.Required("car", default="none"): vol.In(options)}
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
                return await self.async_step_standard_commands_select()
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

    async def async_step_standard_commands_select(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Select standard OBD-II telemetry parameters to monitor."""
        if user_input is not None:
            self._selected_commands = [
                veh_commands[cmd] for cmd in user_input[CONF_COMMANDS]
            ]
            self._configured_commands = []
            if self._selected_commands:
                return await self.async_step_standard_commands_config()
            return await self.async_step_polling()

        commands = [
            veh_commands["RPM"],
            veh_commands["SPEED"],
            veh_commands["COOLANT_TEMP"],
            veh_commands["AMBIENT_AIR_TEMP"],
            veh_commands["ENGINE_LOAD"],
            veh_commands["FUEL_LEVEL"],
            veh_commands["CONTROL_MODULE_VOLTAGE"],
            veh_commands["MAF"],
            veh_commands["RUN_TIME"],
        ]
        commands = sorted(commands, key=lambda cmd: (cmd.name, cmd.mode, cmd.pid))

        options: list[SelectOptionDict] = [
            {
                "value": command.name,
                "label": f"{command.name} ({command.mode} {command.pid})",
            }
            for command in commands
        ]

        return self.async_show_form(
            step_id="standard_commands_select",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_COMMANDS, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    )
                }
            ),
        )

    async def async_step_standard_commands_config(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure standard commands step-by-step."""
        if user_input is not None:
            assert self._command is not None
            self._configured_commands.append(
                {
                    CONF_COMMAND: self._command.name,
                    CONF_ICON: user_input.get(CONF_ICON),
                    CONF_UNIT: user_input.get(CONF_UNIT),
                    CONF_DEVICE_CLASS: user_input.get(CONF_DEVICE_CLASS),
                    CONF_STATE_CLASS: user_input.get(CONF_STATE_CLASS),
                }
            )

            if len(self._selected_commands) == 0:
                return await self.async_step_polling()

        assert len(self._selected_commands) != 0
        self._command = self._selected_commands.pop(0)
        assert self._command is not None

        default_icon = propose_icon_from_command(self._command) or "mdi:car"
        default_units = get_list_of_units(self._command)
        default_unit = default_units[0] if default_units else None

        dev_cls_propose = propose_sensor_device_class(self._command)
        default_device_class = dev_cls_propose.value if dev_cls_propose else None

        state_cls_propose = propose_sensor_state_class(self._command)
        default_state_class = state_cls_propose.value if state_cls_propose else None

        # Prepend 'None' options to allow users to unset device and state classes
        dev_class_options = [selector.SelectOptionDict(value="", label="None")] + [
            selector.SelectOptionDict(
                value=dev_cls.value,
                label=dev_cls.name.replace("_", " ").title(),
            )
            for dev_cls in SensorDeviceClass
        ]

        state_class_options = [selector.SelectOptionDict(value="", label="None")] + [
            selector.SelectOptionDict(
                value=state_cls.value,
                label=state_cls.name.replace("_", " ").title(),
            )
            for state_cls in SensorStateClass
        ]

        return self.async_show_form(
            step_id="standard_commands_config",
            description_placeholders={
                "command_name": " ".join(
                    self._command.name.replace("_", " ").split()
                ).capitalize()
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ICON, default=default_icon
                    ): selector.IconSelector(),
                    vol.Optional(CONF_UNIT, default=default_unit): vol.Any(
                        None, selector.TextSelector()
                    ),
                    vol.Optional(
                        CONF_DEVICE_CLASS, default=default_device_class
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=dev_class_options,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                    vol.Optional(
                        CONF_STATE_CLASS, default=default_state_class
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=state_class_options,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                }
            ),
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
                    CONF_PROFILE: self.selected_profile_json or "{}",
                    CONF_VOLTAGE_CHECK: voltage_check_bool,
                    CONF_FAST_POLL: user_input[CONF_FAST_POLL],
                    CONF_SLOW_POLL: user_input[CONF_SLOW_POLL],
                    CONF_XS_POLL: user_input[CONF_XS_POLL],
                    CONF_VOLTAGE_ON: user_input[CONF_VOLTAGE_ON],
                    CONF_VOLTAGE_OFF: user_input[CONF_VOLTAGE_OFF],
                    CONF_GRACE_PERIOD: user_input[CONF_GRACE_PERIOD],
                    CONF_COMMANDS: self._configured_commands,
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
        return UniversalObdBleOptionsFlow(config_entry)


class UniversalObdBleOptionsFlow(config_entries.OptionsFlow):
    """Handle options adjustment post-setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow parameters."""
        super().__init__()
        self._options = dict(config_entry.options)
        self._selected_commands: list[Command] = []
        self._configured_commands: list[dict[str, str | None]] = []
        self._command: Command | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show main setup options menu."""
        # Clear transient options state to prevent bleeding between menu selections
        self._selected_commands = []
        self._configured_commands = []
        self._command = None

        return self.async_show_menu(
            step_id="init",
            menu_options=["polling", "standard_commands_select", "wican_profile"],
        )

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Polling & Battery Protection Config."""
        if user_input is not None:
            voltage_check_bool = user_input[CONF_VOLTAGE_CHECK] == "AT RV"
            self._options.update(
                {
                    CONF_VOLTAGE_CHECK: voltage_check_bool,
                    CONF_FAST_POLL: user_input[CONF_FAST_POLL],
                    CONF_SLOW_POLL: user_input[CONF_SLOW_POLL],
                    CONF_XS_POLL: user_input[CONF_XS_POLL],
                    CONF_VOLTAGE_ON: user_input[CONF_VOLTAGE_ON],
                    CONF_VOLTAGE_OFF: user_input[CONF_VOLTAGE_OFF],
                    CONF_GRACE_PERIOD: user_input[CONF_GRACE_PERIOD],
                }
            )
            return self.async_create_entry(title="", data=self._options)

        voltage_check = self._options.get(CONF_VOLTAGE_CHECK, True)

        return self.async_show_form(
            step_id="polling",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOLTAGE_CHECK,
                        default="AT RV" if voltage_check else "Disabled",
                    ): vol.In(["AT RV", "Disabled"]),
                    vol.Required(
                        CONF_FAST_POLL,
                        default=self._options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL),
                    ): int,
                    vol.Required(
                        CONF_SLOW_POLL,
                        default=self._options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL),
                    ): int,
                    vol.Required(
                        CONF_XS_POLL,
                        default=self._options.get(CONF_XS_POLL, DEFAULT_XS_POLL),
                    ): int,
                    vol.Required(
                        CONF_VOLTAGE_ON,
                        default=self._options.get(CONF_VOLTAGE_ON, DEFAULT_VOLTAGE_ON),
                    ): float,
                    vol.Required(
                        CONF_VOLTAGE_OFF,
                        default=self._options.get(
                            CONF_VOLTAGE_OFF, DEFAULT_VOLTAGE_OFF
                        ),
                    ): float,
                    vol.Required(
                        CONF_GRACE_PERIOD,
                        default=self._options.get(
                            CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD
                        ),
                    ): int,
                }
            ),
        )

    async def async_step_standard_commands_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle selection of standard diagnostic OBD-II parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if len(user_input[CONF_COMMANDS]) == 0:
                self._options[CONF_COMMANDS] = []
                return self.async_create_entry(title="", data=self._options)

            self._selected_commands = [
                veh_commands[cmd] for cmd in user_input[CONF_COMMANDS]
            ]
            self._configured_commands = []
            return await self.async_step_standard_commands_config()

        coordinator = self.config_entry.runtime_data

        try:
            _, commands = await coordinator.async_get_all_pid_commands(
                force_refresh=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not dynamically query OBD-II commands (car might be off): %s",
                err,
            )
            commands = [
                veh_commands["RPM"],
                veh_commands["SPEED"],
                veh_commands["COOLANT_TEMP"],
                veh_commands["AMBIENT_AIR_TEMP"],
                veh_commands["ENGINE_LOAD"],
                veh_commands["FUEL_LEVEL"],
                veh_commands["CONTROL_MODULE_VOLTAGE"],
                veh_commands["MAF"],
                veh_commands["RUN_TIME"],
            ]

        pre_selected = [
            cmd[CONF_COMMAND] for cmd in self._options.get(CONF_COMMANDS, [])
        ]
        commands = sorted(commands, key=lambda cmd: (cmd.name, cmd.mode, cmd.pid))

        options: list[SelectOptionDict] = [
            {
                "value": command.name,
                "label": f"{command.name} ({command.mode} {command.pid})",
            }
            for command in commands
        ]

        return self.async_show_form(
            step_id="standard_commands_select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMANDS, default=pre_selected
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_standard_commands_config(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure standard commands step-by-step."""
        if user_input is not None:
            assert self._command is not None
            self._configured_commands.append(
                {
                    CONF_COMMAND: self._command.name,
                    CONF_ICON: user_input.get(CONF_ICON),
                    CONF_UNIT: user_input.get(CONF_UNIT),
                    CONF_DEVICE_CLASS: user_input.get(CONF_DEVICE_CLASS),
                    CONF_STATE_CLASS: user_input.get(CONF_STATE_CLASS),
                }
            )

            if len(self._selected_commands) == 0:
                self._options[CONF_COMMANDS] = self._configured_commands
                return self.async_create_entry(title="", data=self._options)

        assert len(self._selected_commands) != 0
        self._command = self._selected_commands.pop(0)
        assert self._command is not None

        previous_config = next(
            (
                cmd_config
                for cmd_config in self._options.get(CONF_COMMANDS, [])
                if cmd_config[CONF_COMMAND] == self._command.name
            ),
            None,
        )

        # Force strict string fallback so default_icon is never None, averting IconSelector UI crashes
        default_icon = (
            previous_config.get(CONF_ICON)
            if previous_config and previous_config.get(CONF_ICON) is not None
            else propose_icon_from_command(self._command)
        ) or "mdi:car"

        default_units = get_list_of_units(self._command)
        default_unit = (
            previous_config.get(CONF_UNIT)
            if previous_config
            else (default_units[0] if default_units else None)
        )

        dev_cls_propose = propose_sensor_device_class(self._command)
        default_device_class = (
            previous_config.get(CONF_DEVICE_CLASS)
            if previous_config
            else (dev_cls_propose.value if dev_cls_propose else None)
        )

        state_cls_propose = propose_sensor_state_class(self._command)
        default_state_class = (
            previous_config.get(CONF_STATE_CLASS)
            if previous_config
            else (state_cls_propose.value if state_cls_propose else None)
        )

        dev_class_options = [selector.SelectOptionDict(value="", label="None")] + [
            selector.SelectOptionDict(
                value=dev_cls.value,
                label=dev_cls.name.replace("_", " ").title(),
            )
            for dev_cls in SensorDeviceClass
        ]

        state_class_options = [selector.SelectOptionDict(value="", label="None")] + [
            selector.SelectOptionDict(
                value=state_cls.value,
                label=state_cls.name.replace("_", " ").title(),
            )
            for state_cls in SensorStateClass
        ]

        return self.async_show_form(
            step_id="standard_commands_config",
            description_placeholders={
                "command_name": " ".join(
                    self._command.name.replace("_", " ").split()
                ).capitalize()
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ICON, default=default_icon
                    ): selector.IconSelector(),
                    vol.Optional(CONF_UNIT, default=default_unit): vol.Any(
                        None, selector.TextSelector()
                    ),
                    vol.Optional(
                        CONF_DEVICE_CLASS, default=default_device_class
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=dev_class_options,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                    vol.Optional(
                        CONF_STATE_CLASS, default=default_state_class
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=state_class_options,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                }
            ),
        )

    async def async_step_wican_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure raw WiCAN profile options."""
        errors = {}
        if user_input is not None:
            try:
                json.loads(user_input[CONF_PROFILE])
                self._options[CONF_PROFILE] = user_input[CONF_PROFILE]
                return self.async_create_entry(title="", data=self._options)
            except json.JSONDecodeError:
                errors["base"] = "invalid_json"

        profile_json = self._options.get(CONF_PROFILE, "{}")

        return self.async_show_form(
            step_id="wican_profile",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROFILE, default=profile_json
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            errors=errors,
        )
