"""Config flow for Universal OBD BLE."""

import logging
from typing import Any
import uuid

from bleak.backends.device import BLEDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict
from homeassistant.helpers.update_coordinator import UpdateFailed

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
    RECOMMENDED_DEFAULTS,
    ConnectionTestResult,
    CustomPid,
    FormulaValidationError,
    UopsConfig,
    all_known_standard_pid_names,
    as_float,
    async_get_characteristics,
    empty_form_defaults,
    fetch_wican_profiles,
    import_wican_profile,
    is_hex,
    list_builtin_profiles,
    load_builtin_profile,
    pid_to_form_defaults,
    probe_connection,
    standard_pid_options,
    validate_formula,
)

_LOGGER = logging.getLogger(__name__)

_NO_PROFILE = "none"
_ACTION_ADD = "__add__"
_ACTION_BACK = "__back__"


def _device_class_options() -> list[SelectOptionDict]:
    """Build the device_class dropdown options, with a leading 'None'."""
    return [SelectOptionDict(value="", label="None")] + [
        SelectOptionDict(
            value=dc.value,
            label=dc.name.replace("_", " ").title(),
        )
        for dc in SensorDeviceClass
    ]


def _state_class_options() -> list[SelectOptionDict]:
    """Build the state_class dropdown options, with a leading 'None'."""
    return [SelectOptionDict(value="", label="None")] + [
        SelectOptionDict(
            value=sc.value,
            label=sc.name.replace("_", " ").title(),
        )
        for sc in SensorStateClass
    ]


class UniversalObdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._address: str | None = None
        self._title: str = "Universal OBD BLE"
        self.atrv_supported: bool = True
        self._uuid_read: str = DEFAULT_UUID_READ
        self._uuid_write: str = DEFAULT_UUID_WRITE
        self._discovered_characteristics: list = []
        self._profile_uops: UopsConfig = UopsConfig()
        self._scanned_supported: list[str] | None = None
        self._wican_profiles: dict[str, dict[str, Any]] = {}

    async def _test_connection(
        self,
        ble_device: BLEDevice,
        uuid_write: str | None = None,
        uuid_read: str | None = None,
    ) -> ConnectionTestResult:
        """Run connection test in executor."""
        return await self.hass.async_add_executor_job(
            probe_connection,
            ble_device,
            self.hass.loop,
            uuid_write or DEFAULT_UUID_WRITE,
            uuid_read or DEFAULT_UUID_READ,
            5.0,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = discovery_info.name or discovery_info.address

        ble_device = discovery_info.device
        result = await self._test_connection(ble_device)
        self._uuid_write = result.uuid_write
        self._uuid_read = result.uuid_read
        self._scanned_supported = result.scanned_supported

        if result.success is None:
            self._discovered_characteristics = await async_get_characteristics(
                ble_device
            )
            return await self.async_step_connection()

        self.atrv_supported = result.success
        return await self.async_step_vehicle()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Standard user setup step - pick a discovered BLE device."""
        errors = {}
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            assert self._address is not None
            ble_device = async_ble_device_from_address(self.hass, self._address, True)
            if not ble_device:
                errors["base"] = "device_not_found"
            else:
                self._title = ble_device.name or self._address
                result = await self._test_connection(ble_device)
                self._uuid_write = result.uuid_write
                self._uuid_read = result.uuid_read
                self._scanned_supported = result.scanned_supported

                if result.success is None:
                    self._discovered_characteristics = await async_get_characteristics(
                        ble_device
                    )
                    return await self.async_step_connection()

                self.atrv_supported = result.success
                return await self.async_step_vehicle()

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
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manual UUID selection when auto-detection fails."""
        if user_input is not None:
            self._uuid_write = user_input[CONF_UUID_WRITE]
            self._uuid_read = user_input[CONF_UUID_READ]

            address = self._address
            assert address is not None
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device:
                result = await self._test_connection(
                    ble_device, self._uuid_write, self._uuid_read
                )
                self.atrv_supported = bool(result.success)
                self._uuid_write = result.uuid_write
                self._uuid_read = result.uuid_read
                self._scanned_supported = result.scanned_supported

            return await self.async_step_vehicle()

        if not self._discovered_characteristics:
            return self.async_abort(reason="no_characteristics_found")

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
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_UUID_WRITE, default=self._uuid_write
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                }
            ),
        )

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick a built-in UOPS profile or a WiCAN-fetched profile."""
        if user_input is not None:
            choice = user_input["profile"]

            if choice == _NO_PROFILE:
                self._profile_uops = UopsConfig()
            else:
                builtin = load_builtin_profile(choice)
                if builtin is not None:
                    self._profile_uops = builtin
                elif choice in self._wican_profiles:
                    self._profile_uops = import_wican_profile(
                        self._wican_profiles[choice]
                    )
                else:
                    self._profile_uops = UopsConfig()

            return await self.async_step_standard_pids()

        builtins = list_builtin_profiles()
        builtin_names = [p["name"] for p in builtins]

        session = async_get_clientsession(self.hass)
        self._wican_profiles = await fetch_wican_profiles(session)

        options: list[SelectOptionDict] = [
            SelectOptionDict(value=_NO_PROFILE, label="None / Standard OBD-II Only")
        ]
        options.extend(
            SelectOptionDict(value=name, label=name) for name in builtin_names
        )
        options.extend(
            SelectOptionDict(value=car_model, label=car_model)
            for car_model in sorted(self._wican_profiles)
            if car_model not in builtin_names
        )

        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile", default=_NO_PROFILE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_standard_pids(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect standard Mode 01 PIDs."""
        if user_input is not None:
            selected = user_input.get("standard_pids", [])
            uops = UopsConfig(
                standard_pids=list(selected),
                custom_pids=list(self._profile_uops.custom_pids),
            )
            return self._async_create_entry(uops)

        scanned = self._scanned_supported
        if scanned:
            candidate_names = scanned
            warning = ""
        else:
            candidate_names = all_known_standard_pid_names()
            warning = (
                "\n\n**Note:** Could not scan the ECU for supported PIDs "
                "(the vehicle may be off). All known standard PIDs are "
                "shown; deselect any that aren't supported by your vehicle."
            )

        preselect_set = set(RECOMMENDED_DEFAULTS) | set(
            self._profile_uops.standard_pids
        )
        preselect = [n for n in preselect_set if n in candidate_names]

        options = [
            SelectOptionDict(value=o["value"], label=o["label"])
            for o in standard_pid_options(candidate_names)
        ]

        return self.async_show_form(
            step_id="standard_pids",
            description_placeholders={"warning": warning},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "standard_pids", default=preselect
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    )
                }
            ),
        )

    def _async_create_entry(self, uops: UopsConfig) -> config_entries.ConfigFlowResult:
        """Create the config entry with device data + UOPS options + polling defaults."""
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_ADDRESS: self._address,
                CONF_ATRV_SUPPORTED: self.atrv_supported,
                CONF_UUID_READ: self._uuid_read,
                CONF_UUID_WRITE: self._uuid_write,
            },
            options={
                CONF_UOPS: uops.to_dict(),
                CONF_VOLTAGE_CHECK: True,
                CONF_FAST_POLL: DEFAULT_FAST_POLL,
                CONF_SLOW_POLL: DEFAULT_SLOW_POLL,
                CONF_XS_POLL: DEFAULT_XS_POLL,
                CONF_VOLTAGE_ON: DEFAULT_VOLTAGE_ON,
                CONF_VOLTAGE_OFF: DEFAULT_VOLTAGE_OFF,
                CONF_GRACE_PERIOD: DEFAULT_GRACE_PERIOD,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: UniversalObdConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return UniversalObdBleOptionsFlow(config_entry)


class UniversalObdBleOptionsFlow(config_entries.OptionsFlow):
    """Handle options adjustment post-setup."""

    def __init__(self, config_entry: UniversalObdConfigEntry) -> None:
        """Initialize options flow state."""
        super().__init__()
        self._options = dict(config_entry.options)
        self._uops = UopsConfig.from_dict(self._options.get(CONF_UOPS, {}))
        self._editing_pid_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["polling", "standard_pids", "custom_pids"],
        )

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Polling intervals + voltage thresholds."""
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
            return self._async_save_options()

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

    async def async_step_standard_pids(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect standard PIDs, with live ECU re-scan for supported ones."""
        if user_input is not None:
            self._uops.standard_pids = list(user_input.get("standard_pids", []))
            self._options[CONF_UOPS] = self._uops.to_dict()
            return self._async_save_options()

        scanned: list[str] | None = None
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None:
            try:
                scanned = await coordinator.async_scan_supported_standard_pids()
            except UpdateFailed as err:
                _LOGGER.warning(
                    "Could not scan supported PIDs (car might be off): %s", err
                )
                scanned = None

        if scanned:
            candidate_names = scanned
            warning = ""
        else:
            candidate_names = all_known_standard_pid_names()
            warning = (
                "\n\n**Note:** Could not scan the ECU for supported PIDs "
                "(the vehicle may be off). All known standard PIDs are "
                "shown; deselect any that aren't supported by your vehicle."
            )

        preselect = [n for n in self._uops.standard_pids if n in candidate_names]

        options = [
            SelectOptionDict(value=o["value"], label=o["label"])
            for o in standard_pid_options(candidate_names)
        ]

        return self.async_show_form(
            step_id="standard_pids",
            description_placeholders={"warning": warning},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "standard_pids", default=preselect
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    )
                }
            ),
        )

    async def async_step_custom_pids(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """List existing custom PIDs + actions dropdown (Add / Edit / Delete)."""
        if user_input is not None:
            action = user_input["action"]
            if action == _ACTION_ADD:
                self._editing_pid_id = None
                return await self.async_step_custom_pid_edit()
            if action == _ACTION_BACK:
                return await self.async_step_init()
            self._editing_pid_id = action
            return await self.async_step_custom_pid_edit()

        sorted_pids = sorted(
            self._uops.custom_pids,
            key=lambda p: (p.can_header or "", p.can_filter or "", p.name),
        )
        options: list[SelectOptionDict] = [
            SelectOptionDict(value=_ACTION_ADD, label="+ Add new custom PID")
        ]
        for pid in sorted_pids:
            header_str = f" [{pid.can_header}]" if pid.can_header else ""
            options.append(
                SelectOptionDict(value=pid.id, label=f"Edit: {pid.name}{header_str}")
            )
        options.append(SelectOptionDict(value=_ACTION_BACK, label="< Back to menu"))

        return self.async_show_form(
            step_id="custom_pids",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "action", default=_ACTION_ADD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_custom_pid_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add or edit a single custom PID, with formula whitelist validation."""
        errors: dict[str, str] = {}

        existing: CustomPid | None = None
        if self._editing_pid_id is not None:
            existing = next(
                (p for p in self._uops.custom_pids if p.id == self._editing_pid_id),
                None,
            )
            if existing is None:
                return await self.async_step_custom_pids()

        if user_input is not None:
            if user_input.get("remove"):
                if existing is not None:
                    self._uops.custom_pids = [
                        p for p in self._uops.custom_pids if p.id != existing.id
                    ]
                    self._options[CONF_UOPS] = self._uops.to_dict()
                    return self._async_save_options()
                return await self.async_step_custom_pids()

            formula = (user_input.get("formula") or "").strip()
            try:
                validate_formula(formula)
            except FormulaValidationError as err:
                errors["formula"] = "invalid_formula"
                _LOGGER.debug("Formula validation failed: %s", err)

            mode = (user_input.get("mode") or "").strip().upper()
            query = (user_input.get("query") or "").strip().upper()
            if not is_hex(mode) or len(mode) != 2:
                errors["mode"] = "invalid_hex"
            if not is_hex(query):
                errors["query"] = "invalid_hex"

            can_header = (user_input.get("can_header") or "").strip().upper()
            can_filter = (user_input.get("can_filter") or "").strip().upper()
            if can_header and not is_hex(can_header):
                errors["can_header"] = "invalid_hex"
            if can_filter and not is_hex(can_filter):
                errors["can_filter"] = "invalid_hex"

            if not errors:
                pid_id = existing.id if existing is not None else uuid.uuid4().hex
                pid = CustomPid(
                    id=pid_id,
                    name=(user_input.get("pid_name") or "").strip() or "Unnamed",
                    mode=mode,
                    query=query,
                    formula=formula,
                    can_header=can_header or None,
                    can_filter=can_filter or None,
                    init_extra=(user_input.get("init_extra") or "").strip() or None,
                    unit=(user_input.get("unit") or "").strip() or None,
                    device_class=user_input.get("device_class") or None,
                    state_class=user_input.get("state_class") or None,
                    min_value=as_float(user_input.get("min_value")),
                    max_value=as_float(user_input.get("max_value")),
                    expected_bytes=int(user_input.get("expected_bytes") or 0),
                    source="manual",
                )
                if existing is not None:
                    self._uops.custom_pids = [
                        pid if p.id == existing.id else p
                        for p in self._uops.custom_pids
                    ]
                else:
                    self._uops.custom_pids.append(pid)
                self._options[CONF_UOPS] = self._uops.to_dict()
                return self._async_save_options()

        defaults = pid_to_form_defaults(existing) if existing else empty_form_defaults()

        return self.async_show_form(
            step_id="custom_pid_edit",
            description_placeholders={
                "action": "Editing" if existing else "Adding",
                "pid_name": existing.name if existing else "new PID",
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "pid_name", default=defaults["pid_name"]
                    ): selector.TextSelector(),
                    vol.Required(
                        "mode", default=defaults["mode"]
                    ): selector.TextSelector(),
                    vol.Required(
                        "query", default=defaults["query"]
                    ): selector.TextSelector(),
                    vol.Optional(
                        "can_header", default=defaults["can_header"]
                    ): selector.TextSelector(),
                    vol.Optional(
                        "can_filter", default=defaults["can_filter"]
                    ): selector.TextSelector(),
                    vol.Optional(
                        "init_extra", default=defaults["init_extra"]
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Required(
                        "formula", default=defaults["formula"]
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        "unit", default=defaults["unit"]
                    ): selector.TextSelector(),
                    vol.Optional(
                        "device_class", default=defaults["device_class"]
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=_device_class_options(),
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                    vol.Optional(
                        "state_class", default=defaults["state_class"]
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=_state_class_options(),
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    ),
                    vol.Optional("min_value", default=defaults["min_value"]): vol.Any(
                        None, float
                    ),
                    vol.Optional("max_value", default=defaults["max_value"]): vol.Any(
                        None, float
                    ),
                    vol.Optional(
                        "expected_bytes", default=defaults["expected_bytes"]
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=64,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="bytes",
                        )
                    ),
                    vol.Optional("remove", default=False): bool,
                }
            ),
            errors=errors,
        )

    def _async_save_options(self) -> config_entries.ConfigFlowResult:
        """Write the working options back to the config entry."""
        self._options[CONF_UOPS] = self._uops.to_dict()
        return self.async_create_entry(title="", data=self._options)
