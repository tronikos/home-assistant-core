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

Typical call sites
------------------

  Config flow (validate only, no bytecode):
      from .uops import validate_formula
      try:
          validate_formula(user_input["formula"])
      except FormulaValidationError as exc:
          errors["formula"] = "invalid_formula"

  Coordinator startup (compile + build plan):
      from .uops import (
          UopsConfig, make_evaluator, context_for_custom_pid,
          CustomQueryItem, StandardQueryItem, build_query_plan,
          get_standard_command,
      )
      uops = UopsConfig.from_dict(entry.options["uops"])
      items: list[QueryItem] = []
      for name in uops.standard_pids:
          cmd = get_standard_command(name)
          if cmd is not None:
              items.append(StandardQueryItem(command_name=name, command=cmd))
      for pid in uops.custom_pids:
          cmd = Command(pid.mode, pid.query)
          items.append(CustomQueryItem(
              pid=pid,
              command=cmd,
              evaluator=make_evaluator(pid.formula),
              context=context_for_custom_pid(pid),
          ))
      self._query_plan = build_query_plan(items)

  Per-poll execution:
      for context, group in self._query_plan:
          if context != self._current_context:
              self._apply_can_context(context)
              self._current_context = context
          for item in group:
              value = item.execute(self.api)
              if value is not None:
                  res_data[item.key] = value
"""

from . import compiler, helpers, importers, profiles, scheduler, schema, standard_pids
from .compiler import (
    FormulaValidationError,
    compile_formula,
    make_evaluator,
    validate_formula,
)
from .helpers import extract_dirty_array, extract_voltage
from .importers import ProfileImporter, WicanImporter, import_wican_profile
from .profiles import list_builtin_profiles, load_builtin_profile
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

__all__ = [
    "RECOMMENDED_DEFAULTS",
    "CanContext",
    "CustomPid",
    "CustomQueryItem",
    "FormulaValidationError",
    "ProfileImporter",
    "QueryItem",
    "StandardQueryItem",
    "UopsConfig",
    "WicanImporter",
    "build_query_plan",
    "compile_formula",
    "compiler",
    "context_for_custom_pid",
    "extract_dirty_array",
    "extract_voltage",
    "get_list_of_units",
    "get_standard_command",
    "helpers",
    "import_wican_profile",
    "importers",
    "list_builtin_profiles",
    "load_builtin_profile",
    "make_evaluator",
    "profiles",
    "propose_device_class",
    "propose_icon",
    "propose_state_class",
    "scan_supported_pids",
    "scheduler",
    "schema",
    "standard_pids",
    "validate_formula",
]
