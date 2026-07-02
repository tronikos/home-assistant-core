"""Unified OBD Parameter Schema (UOPS) - the underlying library.

No `homeassistant.*` imports; depends only on the Python standard
library and the upstream `obdii` (py-obdii) package.

Public surface
--------------

  schema:           CustomPid, UopsConfig
  compiler:         FormulaValidationError, validate_formula,
                    compile_formula, make_evaluator
  scheduler:        CanContext, StandardQueryItem, CustomQueryItem,
                    QueryItem, build_query_plan, context_for_custom_pid
  helpers:          extract_dirty_array, extract_voltage
  standard_pids:    RECOMMENDED_DEFAULTS, get_standard_command,
                    propose_icon, propose_device_class,
                    propose_state_class, get_list_of_units,
                    scan_supported_pids
  importers:        ProfileImporter, WicanImporter, import_wican_profile
  profiles:         list_builtin_profiles, load_builtin_profile
  connection:       ConnectionTestResult, test_connection,
                    async_get_characteristics
  polling:          PollingState, build_query_plan_from_uops,
                    create_connection, apply_can_context,
                    run_query_plan, check_voltage
  profiles_fetch:   WICAN_PROFILES_URL, fetch_wican_profiles
  validation:       is_hex, as_float, all_known_standard_pid_names,
                    standard_pid_options, pid_to_form_defaults,
                    empty_form_defaults, format_sensor_value
  transport_ble:    TransportBLE
"""

from . import (
    compiler,
    connection,
    helpers,
    importers,
    polling,
    profiles,
    profiles_fetch,
    scheduler,
    schema,
    standard_pids,
    transport_ble,
    validation,
)
from .compiler import (
    FormulaValidationError,
    compile_formula,
    make_evaluator,
    validate_formula,
)
from .connection import (
    ConnectionTestResult,
    async_get_characteristics,
    probe_connection,
)
from .helpers import extract_dirty_array, extract_voltage
from .importers import ProfileImporter, WicanImporter, import_wican_profile
from .polling import (
    PollingState,
    apply_can_context,
    build_query_plan_from_uops,
    check_voltage,
    create_connection,
    run_query_plan,
)
from .profiles import list_builtin_profiles, load_builtin_profile
from .profiles_fetch import WICAN_PROFILES_URL, fetch_wican_profiles
from .scheduler import (
    CanContext,
    CustomQueryItem,
    QueryItem,
    StandardQueryItem,
    build_query_plan,
    context_for_custom_pid,
)
from .schema import CustomPid, UopsConfig
from .standard_pids import (
    RECOMMENDED_DEFAULTS,
    get_list_of_units,
    get_standard_command,
    propose_device_class,
    propose_icon,
    propose_state_class,
    scan_supported_pids,
)
from .transport_ble import TransportBLE, TransportError
from .validation import (
    all_known_standard_pid_names,
    as_float,
    empty_form_defaults,
    format_sensor_value,
    is_hex,
    pid_to_form_defaults,
    standard_pid_options,
    user_input_to_form_defaults,
)

__all__ = [
    "RECOMMENDED_DEFAULTS",
    "WICAN_PROFILES_URL",
    "CanContext",
    "ConnectionTestResult",
    "CustomPid",
    "CustomQueryItem",
    "FormulaValidationError",
    "PollingState",
    "ProfileImporter",
    "QueryItem",
    "StandardQueryItem",
    "TransportBLE",
    "TransportError",
    "UopsConfig",
    "WicanImporter",
    "all_known_standard_pid_names",
    "apply_can_context",
    "as_float",
    "async_get_characteristics",
    "build_query_plan",
    "build_query_plan_from_uops",
    "check_voltage",
    "compile_formula",
    "compiler",
    "connection",
    "context_for_custom_pid",
    "create_connection",
    "empty_form_defaults",
    "extract_dirty_array",
    "extract_voltage",
    "fetch_wican_profiles",
    "format_sensor_value",
    "get_list_of_units",
    "get_standard_command",
    "helpers",
    "import_wican_profile",
    "importers",
    "is_hex",
    "list_builtin_profiles",
    "load_builtin_profile",
    "make_evaluator",
    "pid_to_form_defaults",
    "polling",
    "probe_connection",
    "profiles",
    "profiles_fetch",
    "propose_device_class",
    "propose_icon",
    "propose_state_class",
    "run_query_plan",
    "scan_supported_pids",
    "scheduler",
    "schema",
    "standard_pid_options",
    "standard_pids",
    "transport_ble",
    "user_input_to_form_defaults",
    "validate_formula",
    "validation",
]
