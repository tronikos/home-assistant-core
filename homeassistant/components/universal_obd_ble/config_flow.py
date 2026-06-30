"""Config flow for Universal OBD BLE.

Refactored to use the UOPS library. The setup flow is 4 steps:

  1. user / bluetooth  — device discovery + connection test
  2. connection        — UUID fallback (only when auto-detect fails)
  3. vehicle           — pick a built-in UOPS profile, or fetch the
                         WiCAN profile list and translate one into UOPS
  4. standard_pids     — multiselect of standard Mode 01 PIDs,
                         preselected from defaults + profile-derived
                         standards; live ECU scan if reachable

The setup flow does NOT ask for polling/battery config — sensible
defaults are written to entry.options and the user adjusts them via
the options flow. The setup flow does NOT include a JSON editor or
a per-PID 4-field loop — both are gone.

Options flow has 3 menu items:

  - polling        — voltage thresholds + poll intervals
  - standard_pids  — multiselect, live ECU re-scan
  - custom_pids    — master-detail: list -> action -> edit form
                     with formula whitelist validation on save
"""

import contextlib
import logging
from typing import Any
import uuid

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
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict

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
from .obdii.transport_ble import TransportBLE
from .uops import (
    RECOMMENDED_DEFAULTS,
    CustomPid,
    FormulaValidationError,
    UopsConfig,
    get_standard_command,
    import_wican_profile,
    list_builtin_profiles,
    load_builtin_profile,
    scan_supported_pids,
    validate_formula,
)

_LOGGER = logging.getLogger(__name__)

# WiCAN's vehicle_profiles.json — fetched at runtime, translated to
# UOPS via import_wican_profile. Nothing from the source JSON is
# persisted or redistributed; only the resulting UopsConfig is stored
# in the user's HA config entry.
_WICAN_PROFILES_URL = (
    "https://raw.githubusercontent.com/meatpiHQ/wican-fw/"
    "refs/heads/main/vehicle_profiles.json"
)

# Sentinel for the "no profile / standard OBD-II only" choice.
_NO_PROFILE = "none"

# Sentinel for the "add a new custom PID" action in the master-detail
# options flow. Distinct from any real PID id (which is a uuid hex).
_ACTION_ADD = "__add__"
_ACTION_BACK = "__back__"


# ---------------------------------------------------------------------------
# Helpers shared by setup + options flows
# ---------------------------------------------------------------------------


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


def _standard_pid_options(command_names: list[str]) -> list[SelectOptionDict]:
    """Build the standard-PID multiselect options sorted by name."""
    options: list[SelectOptionDict] = []
    for name in sorted(command_names):
        cmd = get_standard_command(name)
        if cmd is None:
            continue
        label = f"{name} ({cmd.mode} {cmd.pid})"
        options.append(SelectOptionDict(value=name, label=label))
    return options


def _all_known_standard_pid_names() -> list[str]:
    """Every standard Mode 01 PID name the obdii registry knows about.

    Used as the fallback list when the ECU is offline and we can't
    scan supported PIDs.
    """
    names: list[str] = []
    for cmd in veh_commands[1]:
        if cmd.name == "Unnamed":
            continue
        if cmd.name.startswith("SUPPORTED_PIDS"):
            continue
        names.append(cmd.name)
    return names


async def _async_fetch_wican_profiles(hass) -> dict[str, dict[str, Any]]:
    """Fetch WiCAN's vehicle_profiles.json, return {car_model: raw_dict}.

    Returns {} on any failure (network, parse, shape mismatch) — the
    caller falls back to built-in profiles only. Nothing from the
    source JSON is persisted; only the translated UopsConfig is.
    """
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            _WICAN_PROFILES_URL, timeout=ClientTimeout(total=5)
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("WiCAN profile fetch returned status %s", resp.status)
                return {}
            # content_type=None allows text/plain MIME (GitHub raw does this)
            data = await resp.json(content_type=None)
        if not (
            isinstance(data, dict) and "cars" in data and isinstance(data["cars"], list)
        ):
            _LOGGER.warning("WiCAN profile JSON has unexpected shape")
            return {}
        return {car["car_model"]: car for car in data["cars"] if "car_model" in car}
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not download WiCAN profiles: %s", err)
        return {}


def _wican_profile_to_uops(raw: dict[str, Any]) -> UopsConfig:
    """Translate a WiCAN profile dict to UopsConfig via the importer."""
    return import_wican_profile(raw)


# ===========================================================================
# SETUP FLOW
# ===========================================================================


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
        self._discovered_characteristics: list[BleakGATTCharacteristic] = []
        # The UOPS config built from the chosen vehicle profile — read
        # by async_step_standard_pids to derive the preselected set.
        self._profile_uops: UopsConfig = UopsConfig()
        # Cached supported-PID scan result (from the connection test).
        self._scanned_supported: list[str] | None = None
        self._wican_profiles: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Connection test (preserved from pre-refactor)
    # ------------------------------------------------------------------

    def _test_connection_sync(
        self, ble_device, uuid_write=None, uuid_read=None
    ) -> tuple[bool | None, str, str, list[str] | None]:
        """Thread-safe connection test.

        Returns (success, final_uuid_write, final_uuid_read, scanned_supported).
        `success` is None if the connection itself failed; True/False if
        the connection worked and AT RV returned a plausible voltage / "?".
        `scanned_supported` is the list of supported Mode 01 PID names
        if the scan succeeded, else None.
        """
        resp: Response | None = None
        scanned: list[str] | None = None
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
            final_write = transport.config.get("uuid_write", final_write)
            final_read = transport.config.get("uuid_read", final_read)
            resp = conn.query(Command(Mode.AT, "RV"))

            # Best-effort supported-PID scan — non-fatal if it fails
            # (car may be off, ECU may not respond to Mode 01 PID 00).
            try:
                scanned = scan_supported_pids(conn)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Supported-PID scan during setup failed: %s", err)
                scanned = None
        except Exception as e:  # noqa: BLE001
            _LOGGER.debug("Connection test failed: %s", e)
            return None, final_write, final_read, None
        finally:
            if conn:
                with contextlib.suppress(Exception):
                    conn.close()

        success = resp is not None and b"?" not in resp.raw
        return success, final_write, final_read, scanned

    async def _async_get_characteristics(
        self, ble_device
    ) -> list[BleakGATTCharacteristic]:
        """Fetch GATT characteristics via the BLE service cache."""
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
            _LOGGER.error("Failed to fetch GATT characteristics: %s", err)
            return []
        else:
            return characteristics
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.disconnect()

    # ------------------------------------------------------------------
    # Step 1: device discovery (user or bluetooth)
    # ------------------------------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._title = discovery_info.name or discovery_info.address

        ble_device = discovery_info.device
        (
            success,
            final_write,
            final_read,
            scanned,
        ) = await self.hass.async_add_executor_job(
            self._test_connection_sync, ble_device
        )
        self._uuid_write = final_write
        self._uuid_read = final_read
        self._scanned_supported = scanned

        if success is None:
            self._discovered_characteristics = await self._async_get_characteristics(
                ble_device
            )
            return await self.async_step_connection()

        self.atrv_supported = success
        return await self.async_step_vehicle()

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Standard user setup step — pick a discovered BLE device."""
        errors = {}
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            assert self._address is not None
            ble_device = async_ble_device_from_address(self.hass, self._address, True)
            if not ble_device:
                errors["base"] = "device_not_found"
            else:
                self._title = ble_device.name or self._address
                (
                    success,
                    final_write,
                    final_read,
                    scanned,
                ) = await self.hass.async_add_executor_job(
                    self._test_connection_sync, ble_device
                )
                self._uuid_write = final_write
                self._uuid_read = final_read
                self._scanned_supported = scanned

                if success is None:
                    self._discovered_characteristics = (
                        await self._async_get_characteristics(ble_device)
                    )
                    return await self.async_step_connection()

                self.atrv_supported = success
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

    # ------------------------------------------------------------------
    # Step 2: UUID fallback (conditional)
    # ------------------------------------------------------------------

    async def async_step_connection(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Manual UUID selection when auto-detection fails."""
        if user_input is not None:
            self._uuid_write = user_input[CONF_UUID_WRITE]
            self._uuid_read = user_input[CONF_UUID_READ]

            address = self._address
            assert address is not None
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device:
                (
                    success,
                    final_write,
                    final_read,
                    scanned,
                ) = await self.hass.async_add_executor_job(
                    self._test_connection_sync,
                    ble_device,
                    self._uuid_write,
                    self._uuid_read,
                )
                self.atrv_supported = bool(success)
                self._uuid_write = final_write
                self._uuid_read = final_read
                self._scanned_supported = scanned

            return await self.async_step_vehicle()

        if not self._discovered_characteristics:
            return self.async_abort(reason="no_characteristics_found")

        # Single dropdown of (read, write) candidate pairs, preselected
        # to the highest-confidence pair. The user can override to any
        # individual characteristic UUID.
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

    # ------------------------------------------------------------------
    # Step 3: vehicle profile selection
    # ------------------------------------------------------------------

    async def async_step_vehicle(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Pick a built-in UOPS profile or a WiCAN-fetched profile.

        WiCAN profiles are translated to UOPS at selection time via
        import_wican_profile; nothing from the source JSON is persisted.
        The chosen profile's standard_pids (after reverse de-dup) feed
        into the next step's preselected set.
        """
        if user_input is not None:
            choice = user_input["profile"]

            if choice == _NO_PROFILE:
                self._profile_uops = UopsConfig()
            else:
                # Built-in profiles are loaded by name; WiCAN-fetched
                # ones are translated on the fly. We stash both kinds
                # in self._wican_profiles as raw dicts, keyed by
                # car_model — but built-ins take precedence.
                builtin = load_builtin_profile(choice)
                if builtin is not None:
                    self._profile_uops = builtin
                elif choice in self._wican_profiles:
                    self._profile_uops = _wican_profile_to_uops(
                        self._wican_profiles[choice]
                    )
                else:
                    self._profile_uops = UopsConfig()

            return await self.async_step_standard_pids()

        # Build the dropdown: built-in profiles first, then WiCAN-fetched.
        builtins = list_builtin_profiles()
        builtin_names = [p["name"] for p in builtins]

        # Fetch WiCAN profiles (best-effort, 5s timeout).
        self._wican_profiles = await _async_fetch_wican_profiles(self.hass)

        options: list[SelectOptionDict] = [
            SelectOptionDict(
                value=_NO_PROFILE,
                label="None / Standard OBD-II Only",
            )
        ]
        options.extend(
            SelectOptionDict(value=name, label=name) for name in builtin_names
        )
        for car_model in sorted(self._wican_profiles):
            # Skip if a built-in profile already has this name — built-ins win.
            if car_model in builtin_names:
                continue
            options.append(SelectOptionDict(value=car_model, label=car_model))

        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile", default=_NO_PROFILE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 4: standard PIDs multiselect
    # ------------------------------------------------------------------

    async def async_step_standard_pids(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect standard Mode 01 PIDs.

        Preselects:
          - RECOMMENDED_DEFAULTS (9 sensible defaults)
          - any standard PIDs the chosen profile declared (post reverse-de-dup)

        Filters the dropdown to only PIDs the ECU claims to support,
        if the scan during the connection test succeeded. If the scan
        failed (car off, ECU unreachable), shows all known PIDs with a
        warning in the description.
        """
        if user_input is not None:
            selected = user_input.get("standard_pids", [])
            # Merge selected standard PIDs with the profile's custom PIDs.
            uops = UopsConfig(
                standard_pids=list(selected),
                custom_pids=list(self._profile_uops.custom_pids),
            )
            return self._async_create_entry(uops)

        # Build the candidate list.
        scanned = self._scanned_supported
        if scanned:
            candidate_names = scanned
            warning = ""
        else:
            candidate_names = _all_known_standard_pid_names()
            warning = (
                "\n\n**Note:** Could not scan the ECU for supported PIDs "
                "(the vehicle may be off). All known standard PIDs are "
                "shown; deselect any that aren't supported by your vehicle."
            )

        # Preselect: defaults U profile-derived standards, intersected
        # with the candidate list so we never preselect a PID that
        # isn't even shown.
        preselect_set = set(RECOMMENDED_DEFAULTS) | set(
            self._profile_uops.standard_pids
        )
        preselect = [n for n in preselect_set if n in candidate_names]

        options = _standard_pid_options(candidate_names)

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

    # ------------------------------------------------------------------
    # Entry creation
    # ------------------------------------------------------------------

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
                # Polling defaults — user adjusts via options flow.
                CONF_VOLTAGE_CHECK: True,
                CONF_FAST_POLL: DEFAULT_FAST_POLL,
                CONF_SLOW_POLL: DEFAULT_SLOW_POLL,
                CONF_XS_POLL: DEFAULT_XS_POLL,
                CONF_VOLTAGE_ON: DEFAULT_VOLTAGE_ON,
                CONF_VOLTAGE_OFF: DEFAULT_VOLTAGE_OFF,
                CONF_GRACE_PERIOD: DEFAULT_GRACE_PERIOD,
            },
        )

    # ------------------------------------------------------------------
    # Options flow handoff
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return UniversalObdBleOptionsFlow(config_entry)


# ===========================================================================
# OPTIONS FLOW
# ===========================================================================


class UniversalObdBleOptionsFlow(config_entries.OptionsFlow):
    """Handle options adjustment post-setup.

    Three menu items:
      - polling       — voltage + poll intervals
      - standard_pids — multiselect with live ECU re-scan
      - custom_pids   — master-detail Add/Edit/Delete with formula validation
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow state."""
        super().__init__()
        self._options = dict(config_entry.options)
        # The working copy of the UOPS config — mutated by the custom
        # PID add/edit/delete steps, then written back to options on save.
        self._uops = UopsConfig.from_dict(self._options.get(CONF_UOPS, {}))
        # Track the PID currently being edited (by id), or None for "add new".
        self._editing_pid_id: str | None = None

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["polling", "standard_pids", "custom_pids"],
        )

    # ------------------------------------------------------------------
    # Polling & battery guard
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Standard PIDs multiselect (with live ECU re-scan)
    # ------------------------------------------------------------------

    async def async_step_standard_pids(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Multiselect standard PIDs, with live ECU re-scan for supported ones."""
        if user_input is not None:
            self._uops.standard_pids = list(user_input.get("standard_pids", []))
            self._options[CONF_UOPS] = self._uops.to_dict()
            return self._async_save_options()

        # Try a live scan via the coordinator.
        scanned: list[str] | None = None
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None:
            try:
                scanned = await coordinator.async_scan_supported_standard_pids()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not scan supported PIDs (car might be off): %s", err
                )
                scanned = None

        if scanned:
            candidate_names = scanned
            warning = ""
        else:
            candidate_names = _all_known_standard_pid_names()
            warning = (
                "\n\n**Note:** Could not scan the ECU for supported PIDs "
                "(the vehicle may be off). All known standard PIDs are "
                "shown; deselect any that aren't supported by your vehicle."
            )

        # Preselect the currently-configured standard PIDs (intersected
        # with the candidate list so we don't preselect invisible items).
        preselect = [n for n in self._uops.standard_pids if n in candidate_names]

        options = _standard_pid_options(candidate_names)

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

    # ------------------------------------------------------------------
    # Custom PIDs — master-detail controller
    # ------------------------------------------------------------------

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
            # Otherwise: action is a PID id — go to the edit form for it.
            self._editing_pid_id = action
            return await self.async_step_custom_pid_edit()

        # Build the actions dropdown: Add + one entry per existing PID.
        # Sort existing PIDs by CAN header so PIDs sharing a header
        # group visually — a small UI nudge toward the CAN-grouping
        # concept the scheduler uses.
        sorted_pids = sorted(
            self._uops.custom_pids,
            key=lambda p: (p.can_header or "", p.can_filter or "", p.name),
        )
        options: list[SelectOptionDict] = [
            SelectOptionDict(
                value=_ACTION_ADD,
                label="+ Add new custom PID",
            )
        ]
        for pid in sorted_pids:
            header_str = f" [{pid.can_header}]" if pid.can_header else ""
            options.append(
                SelectOptionDict(
                    value=pid.id,
                    label=f"Edit: {pid.name}{header_str}",
                )
            )
        options.append(SelectOptionDict(value=_ACTION_BACK, label="← Back to menu"))

        return self.async_show_form(
            step_id="custom_pids",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "action", default=_ACTION_ADD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
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

        # Are we editing an existing PID or adding a new one?
        existing: CustomPid | None = None
        if self._editing_pid_id is not None:
            existing = next(
                (p for p in self._uops.custom_pids if p.id == self._editing_pid_id),
                None,
            )
            if existing is None:
                # Stale id — bail back to the list.
                return await self.async_step_custom_pids()

        if user_input is not None:
            # "Remove this custom PID" checkbox
            if user_input.get("remove"):
                if existing is not None:
                    self._uops.custom_pids = [
                        p for p in self._uops.custom_pids if p.id != existing.id
                    ]
                    self._options[CONF_UOPS] = self._uops.to_dict()
                    return self._async_save_options()
                return await self.async_step_custom_pids()

            # Validate the formula (stages 1+2 — no bytecode compile here,
            # that happens at coordinator startup).
            formula = (user_input.get("formula") or "").strip()
            try:
                validate_formula(formula)
            except FormulaValidationError as err:
                errors["formula"] = "invalid_formula"
                _LOGGER.debug("Formula validation failed: %s", err)

            # Validate mode + query are hex.
            mode = (user_input.get("mode") or "").strip().upper()
            query = (user_input.get("query") or "").strip().upper()
            if not _is_hex(mode) or len(mode) != 2:
                errors["mode"] = "invalid_hex"
            if not _is_hex(query):
                errors["query"] = "invalid_hex"

            # Validate CAN header + filter are hex (if non-empty).
            can_header = (user_input.get("can_header") or "").strip().upper()
            can_filter = (user_input.get("can_filter") or "").strip().upper()
            if can_header and not _is_hex(can_header):
                errors["can_header"] = "invalid_hex"
            if can_filter and not _is_hex(can_filter):
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
                    min_value=_as_float(user_input.get("min_value")),
                    max_value=_as_float(user_input.get("max_value")),
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

        # Build the form, pre-filling from `existing` if editing.
        defaults = (
            _pid_to_form_defaults(existing) if existing else _empty_form_defaults()
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

    # ------------------------------------------------------------------
    # Save helper
    # ------------------------------------------------------------------

    def _async_save_options(self) -> config_entries.ConfigFlowResult:
        """Write the working options back to the config entry."""
        # Always reflect the latest UOPS in options before saving.
        self._options[CONF_UOPS] = self._uops.to_dict()
        return self.async_create_entry(title="", data=self._options)


# ---------------------------------------------------------------------------
# Small form helpers
# ---------------------------------------------------------------------------


def _is_hex(s: str) -> bool:
    """True if s is a non-empty string of hex digits."""
    if not s:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    else:
        return True


def _as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except TypeError, ValueError:
        return None


def _pid_to_form_defaults(pid: CustomPid) -> dict[str, Any]:
    """Pre-fill the edit form from an existing CustomPid."""
    return {
        "pid_name": pid.name,
        "mode": pid.mode,
        "query": pid.query,
        "can_header": pid.can_header or "",
        "can_filter": pid.can_filter or "",
        "init_extra": pid.init_extra or "",
        "formula": pid.formula,
        "unit": pid.unit or "",
        "device_class": pid.device_class or "",
        "state_class": pid.state_class or "",
        "min_value": pid.min_value,
        "max_value": pid.max_value,
        "expected_bytes": pid.expected_bytes or 0,
    }


def _empty_form_defaults() -> dict[str, Any]:
    """Defaults for a brand-new custom PID form."""
    return {
        "pid_name": "",
        "mode": "22",
        "query": "",
        "can_header": "",
        "can_filter": "",
        "init_extra": "",
        "formula": "B(0)",
        "unit": "",
        "device_class": "",
        "state_class": "",
        "min_value": None,
        "max_value": None,
        "expected_bytes": 0,
    }
