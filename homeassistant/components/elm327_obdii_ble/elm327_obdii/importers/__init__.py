"""Profile importers - translate upstream formats into ProfileConfig.

Each importer is the only place that knows its upstream schema shape.
Everything downstream works purely with ProfileConfig.

Currently implemented:
  - WiCAN JSON  (meatpiHQ/wican-fw vehicle_profiles.json)

The schema is shaped to accept future importers (Torque CSV, RealDash
XML) without changes - see uops/importers/base.py for the Protocol.
"""

from .base import ProfileImporter
from .wican import WicanImporter, import_wican_profile

__all__ = ["ProfileImporter", "WicanImporter", "import_wican_profile"]
