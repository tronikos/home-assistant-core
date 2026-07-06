"""Pytest configuration for the elm327_obdii library tests.

Adds the bundled ``elm327_obdii`` package (which lives inside the HA
integration directory at ``elm327_obdii_ble/elm327_obdii_ble``) to
``sys.path`` so tests can import it without installing the integration.
"""

from pathlib import Path
import sys

_LIB_ROOT = Path(__file__).resolve().parents[4] / "elm327_obdii_ble"
if str(_LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(_LIB_ROOT))


def pytest_addoption(parser):
    """Add a --run-network flag to enable live network tests."""
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="Run tests that require network access (e.g. live profile fetch)",
    )


def pytest_configure(config):
    """Register the 'network' marker."""
    config.addinivalue_line(
        "markers",
        "network: tests that require network access (deselected by default)",
    )
