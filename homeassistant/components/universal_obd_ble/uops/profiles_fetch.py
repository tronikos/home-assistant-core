"""Fetch WiCAN vehicle profiles from GitHub.

Pure-async helper; takes an aiohttp ClientSession (HA-agnostic).
"""

import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

WICAN_PROFILES_URL = (
    "https://raw.githubusercontent.com/meatpiHQ/wican-fw/"
    "refs/heads/main/vehicle_profiles.json"
)


async def fetch_wican_profiles(session: ClientSession) -> dict[str, dict[str, Any]]:
    """Fetch WiCAN's vehicle_profiles.json, return {car_model: raw_dict}.

    Returns {} on any failure (network, parse, shape mismatch). Nothing
    from the source JSON is persisted; only the translated UopsConfig is.
    """
    try:
        async with session.get(
            WICAN_PROFILES_URL, timeout=ClientTimeout(total=5)
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("WiCAN profile fetch returned status %s", resp.status)
                return {}
            data = await resp.json(content_type=None)
        if not (
            isinstance(data, dict) and "cars" in data and isinstance(data["cars"], list)
        ):
            _LOGGER.warning("WiCAN profile JSON has unexpected shape")
            return {}
        return {car["car_model"]: car for car in data["cars"] if "car_model" in car}
    except (ClientError, TimeoutError, ValueError) as err:
        _LOGGER.warning("Could not download WiCAN profiles: %s", err)
        return {}
