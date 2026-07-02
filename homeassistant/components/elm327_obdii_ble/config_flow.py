"""Config flow for the ELM327 OBD-II BLE integration."""

import logging
from typing import TYPE_CHECKING, Any
import uuid

from bleak.backends.device import BLEDevice
from bluetooth_data_tools import human_readable_name
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
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import SelectOptionDict
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
    DEFAULT_GRACE_PERIOD,
    DEFAULT_UUID_READ,
    DEFAULT_UUID_WRITE,
    DEFAULT_VOLTAGE_OFF,
    DEFAULT_VOLTAGE_ON,
    DOMAIN,
)
from .elm327_obdii import (
    RECOMMENDED_DEFAULTS,
    ConnectionTestResult,
    CustomPid,
    FormulaValidationError,
    ProfileConfig,
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
    probe_adapter,
    standard_pid_options,
    user_input_to_form_defaults,
    validate_formula,
)

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)

_NO_PROFILE = "none"
_IMPORT_WICAN = "__import_wican__"
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


class Elm327ObdiiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._address: str | None = None
        self._title: str = "ELM327 OBD-II BLE"
        self.atrv_supported: bool = True
        self._uuid_read: str = DEFAULT_UUID_READ
        self._uuid_write: str = DEFAULT_UUID_WRITE
        self._discovered_characteristics: list = []
        self._profile_config: ProfileConfig = ProfileConfig()
        self._selected_standard_pids: list[str] = []
        self._scanned_supported: list[str] | None = None
        self._wican_profiles: dict[str, dict[str, Any]] = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def _test_connection(
        self,
        ble_device: BLEDevice,
        uuid_write: str | None = None,
        uuid_read: str | None = None,
    ) -> ConnectionTestResult:
        """Run the connection test in the executor pool."""
        return await self.hass.async_add_executor_job(
            probe_adapter,
            ble_device,
            self.hass.loop,
            uuid_write or DEFAULT_UUID_WRITE,
            uuid_read or DEFAULT_UUID_READ,
            5.0,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle bluetooth discovery - just record the device and ask the user to confirm."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = human_readable_name(
            None, discovery_info.name, discovery_info.address
        )
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm a discovered ELM327 adapter and probe it on submit."""
        assert self._discovery_info is not None
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders=self.context["title_placeholders"],
            )

        ble_device = self._discovery_info.device
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
        errors: dict[str, str] = {}
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(
                format_mac(self._address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            ble_device = async_ble_device_from_address(self.hass, self._address, True)
            if not ble_device:
                errors["base"] = "device_not_found"
            else:
                self._title = human_readable_name(None, ble_device.name, self._address)
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
            dev.address: human_readable_name(None, dev.name, dev.address)
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

            # Reached only after async_step_user/bluetooth set self._address.
            assert self._address is not None
            ble_device = async_ble_device_from_address(self.hass, self._address, True)
            if ble_device is None:
                return self.async_abort(reason="device_not_found")

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
            SelectOptionDict(
                value=char.uuid,
                label=f"{char.description or 'Unknown Characteristic'} ({char.uuid.split('-')[0]})",
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
        """Pick a built-in profile, none, or choose to import from WiCAN."""
        if user_input is not None:
            choice = user_input["profile"]

            if choice == _NO_PROFILE:
                self._profile_config = ProfileConfig()
                return await self.async_step_standard_pids()

            if choice == _IMPORT_WICAN:
                # Defer the WiCAN fetch to the next step so we only hit
                # the network when the user actually wants a WiCAN profile.
                return await self.async_step_wican()

            builtin = await self.hass.async_add_executor_job(
                load_builtin_profile, choice
            )
            self._profile_config = builtin if builtin is not None else ProfileConfig()
            return await self.async_step_standard_pids()

        builtins = await self.hass.async_add_executor_job(list_builtin_profiles)

        options: list[SelectOptionDict] = [
            SelectOptionDict(value=_NO_PROFILE, label="None / Standard OBD-II Only")
        ]
        options.extend(
            SelectOptionDict(value=p["name"], label=p["name"]) for p in builtins
        )
        options.append(
            SelectOptionDict(
                value=_IMPORT_WICAN, label="Import from WiCAN repository..."
            )
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

    async def async_step_wican(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Fetch WiCAN profiles and let the user pick one to import.

        Only reached when the user selected "Import from WiCAN
        repository..." on the vehicle step. If the fetch returns no
        profiles (network error, unexpected shape), the user is bounced
        back to the vehicle step with an error.
        """
        if user_input is not None:
            choice = user_input["profile"]
            if choice in self._wican_profiles:
                self._profile_config = import_wican_profile(
                    self._wican_profiles[choice]
                )
            else:
                self._profile_config = ProfileConfig()
            return await self.async_step_standard_pids()

        session = async_get_clientsession(self.hass)
        self._wican_profiles = await fetch_wican_profiles(session)

        if not self._wican_profiles:
            # Network/parse failure - send the user back to the vehicle
            # step. (We use a no-op form here; the user re-picks on the
            # previous step.)
            return self.async_abort(reason="wican_fetch_failed")

        options: list[SelectOptionDict] = [
            SelectOptionDict(value=car_model, label=car_model)
            for car_model in sorted(self._wican_profiles)
        ]

        return self.async_show_form(
            step_id="wican",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile", default=options[0]["value"]
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
            self._selected_standard_pids = list(user_input["standard_pids"])
            return await self.async_step_custom_pids_select()

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
            self._profile_config.standard_pids
        )
        # Iterate over candidate_names (sorted) for deterministic order.
        preselect = [n for n in candidate_names if n in preselect_set]

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

    async def async_step_custom_pids_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect which custom PIDs from the profile to enable."""
        if not self._profile_config.custom_pids:
            profile = ProfileConfig(
                standard_pids=list(self._selected_standard_pids),
                custom_pids=[],
            )
            return self._async_create_entry(profile)

        if user_input is not None:
            selected_ids = set(user_input["custom_pids"])
            selected_custom = [
                pid
                for pid in self._profile_config.custom_pids
                if pid.id in selected_ids
            ]
            profile = ProfileConfig(
                standard_pids=list(self._selected_standard_pids),
                custom_pids=selected_custom,
            )
            return self._async_create_entry(profile)

        sorted_pids = sorted(self._profile_config.custom_pids, key=lambda p: p.name)
        options = [
            SelectOptionDict(
                value=pid.id,
                label=f"{pid.name} ({pid.mode} {pid.query})",
            )
            for pid in sorted_pids
        ]
        preselect = [pid.id for pid in sorted_pids]

        return self.async_show_form(
            step_id="custom_pids_select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "custom_pids", default=preselect
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

    def _async_create_entry(
        self, profile: ProfileConfig
    ) -> config_entries.ConfigFlowResult:
        """Create the config entry with device data + profile + battery defaults."""
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_ADDRESS: self._address,
                CONF_ATRV_SUPPORTED: self.atrv_supported,
                CONF_UUID_READ: self._uuid_read,
                CONF_UUID_WRITE: self._uuid_write,
            },
            options={
                CONF_PROFILE: profile.to_dict(),
                CONF_VOLTAGE_CHECK: True,
                CONF_VOLTAGE_ON: DEFAULT_VOLTAGE_ON,
                CONF_VOLTAGE_OFF: DEFAULT_VOLTAGE_OFF,
                CONF_GRACE_PERIOD: DEFAULT_GRACE_PERIOD,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Elm327ObdiiConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return Elm327ObdiiOptionsFlow(config_entry)


class Elm327ObdiiOptionsFlow(config_entries.OptionsFlow):
    """Handle options adjustment post-setup."""

    def __init__(self, config_entry: Elm327ObdiiConfigEntry) -> None:
        """Initialize options flow state."""
        super().__init__()
        self._options = dict(config_entry.options)
        self._profile = ProfileConfig.from_dict(self._options[CONF_PROFILE])
        self._editing_pid_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["battery", "standard_pids", "custom_pids"],
        )

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure the 12V auxiliary battery guard (voltage check + thresholds)."""
        if user_input is not None:
            self._options.update(
                {
                    CONF_VOLTAGE_CHECK: user_input[CONF_VOLTAGE_CHECK],
                    CONF_VOLTAGE_ON: user_input[CONF_VOLTAGE_ON],
                    CONF_VOLTAGE_OFF: user_input[CONF_VOLTAGE_OFF],
                    CONF_GRACE_PERIOD: user_input[CONF_GRACE_PERIOD],
                }
            )
            return self._async_save_options()

        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOLTAGE_CHECK,
                        default=self._options[CONF_VOLTAGE_CHECK],
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_VOLTAGE_ON,
                        default=self._options[CONF_VOLTAGE_ON],
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10.0, max=15.0, step=0.1, unit_of_measurement="V"
                        )
                    ),
                    vol.Required(
                        CONF_VOLTAGE_OFF,
                        default=self._options[CONF_VOLTAGE_OFF],
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10.0, max=15.0, step=0.1, unit_of_measurement="V"
                        )
                    ),
                    vol.Required(
                        CONF_GRACE_PERIOD,
                        default=self._options[CONF_GRACE_PERIOD],
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=600, step=1, unit_of_measurement="s"
                        )
                    ),
                }
            ),
        )

    async def async_step_standard_pids(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect standard PIDs, with live ECU re-scan for supported ones."""
        if user_input is not None:
            self._profile.standard_pids = list(user_input["standard_pids"])
            self._options[CONF_PROFILE] = self._profile.to_dict()
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

        preselect = [n for n in self._profile.standard_pids if n in candidate_names]

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
            self._profile.custom_pids,
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
                (p for p in self._profile.custom_pids if p.id == self._editing_pid_id),
                None,
            )
            if existing is None:
                return await self.async_step_custom_pids()

        if user_input is not None:
            if user_input["remove"]:
                if existing is not None:
                    self._profile.custom_pids = [
                        p for p in self._profile.custom_pids if p.id != existing.id
                    ]
                    self._options[CONF_PROFILE] = self._profile.to_dict()
                    return self._async_save_options()
                return await self.async_step_custom_pids()

            formula = (user_input["formula"] or "").strip()
            try:
                validate_formula(formula)
            except FormulaValidationError as err:
                errors["formula"] = "invalid_formula"
                _LOGGER.debug("Formula validation failed: %s", err)

            mode = (user_input["mode"] or "").strip().upper()
            query = (user_input["query"] or "").strip().upper()
            if not is_hex(mode) or len(mode) != 2:
                errors["mode"] = "invalid_hex"
            if not is_hex(query):
                errors["query"] = "invalid_hex"

            can_header = (user_input["can_header"] or "").strip().upper()
            can_filter = (user_input["can_filter"] or "").strip().upper()
            if can_header and not is_hex(can_header):
                errors["can_header"] = "invalid_hex"
            if can_filter and not is_hex(can_filter):
                errors["can_filter"] = "invalid_hex"

            if not errors:
                pid_id = existing.id if existing is not None else uuid.uuid4().hex
                pid = CustomPid(
                    id=pid_id,
                    name=(user_input["pid_name"] or "").strip() or "Unnamed",
                    mode=mode,
                    query=query,
                    formula=formula,
                    can_header=can_header or None,
                    can_filter=can_filter or None,
                    init_extra=(user_input["init_extra"] or "").strip() or None,
                    unit=(user_input["unit"] or "").strip() or None,
                    device_class=user_input["device_class"] or None,
                    state_class=user_input["state_class"] or None,
                    min_value=as_float(user_input["min_value"]),
                    max_value=as_float(user_input["max_value"]),
                    expected_bytes=int(user_input["expected_bytes"] or 0),
                    source="manual",
                )
                if existing is not None:
                    self._profile.custom_pids = [
                        pid if p.id == existing.id else p
                        for p in self._profile.custom_pids
                    ]
                else:
                    self._profile.custom_pids.append(pid)
                self._options[CONF_PROFILE] = self._profile.to_dict()
                return self._async_save_options()

        # On validation error, preserve the user's submitted input rather
        # than resetting to stored/empty defaults.
        if user_input is not None and errors:
            defaults = user_input_to_form_defaults(user_input)
        else:
            defaults = (
                pid_to_form_defaults(existing) if existing else empty_form_defaults()
            )

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
        self._options[CONF_PROFILE] = self._profile.to_dict()
        return self.async_create_entry(title="", data=self._options)
