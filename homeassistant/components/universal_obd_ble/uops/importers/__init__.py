"""Profile importers — translate upstream formats into UopsConfig.

Each importer is the ONLY place in the codebase that knows its upstream
schema shape. Everything downstream works purely with UopsConfig.

Currently implemented:
  - WiCAN JSON  (meatpiHQ/wican-fw vehicle_profiles.json)

Future importers (NOT implemented, but the schema is shaped to accept
them — see uops/importers/base.py for the Protocol):
  - Torque extended-PID CSV
  - RealDash custom-channel XML
"""

from .base import ProfileImporter
from .wican import WicanImporter, import_wican_profile

__all__ = ["ProfileImporter", "WicanImporter", "import_wican_profile"]
