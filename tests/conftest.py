"""
conftest.py — Centraliserad mock-setup och modul-laddning.

Körs EN gång innan alla tester. Alla testfiler kan sedan importera direkt
från tibber_extended.sensor / tibber_extended.binary_sensor.
"""
import sys
import os
import types
import importlib.util
from unittest.mock import MagicMock
from datetime import datetime, timezone
from dateutil.parser import isoparse


# =============================================================
# Stub-klasser för Home Assistant-entiteter
# =============================================================

class _SensorEntity:
    @property
    def native_unit_of_measurement(self):
        return getattr(self, "_attr_native_unit_of_measurement", None)

class _BinarySensorEntity:
    @property
    def name(self):
        return getattr(self, "_attr_name", None)
    def async_on_remove(self, func):
        pass

class _RestoreEntity:
    """Stub för RestoreEntity — sparar/återställer state över omstarter."""
    async def async_get_last_state(self):
        return None
    async def async_added_to_hass(self):
        pass
    def async_on_remove(self, func):
        pass

class _CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

class _DataUpdateCoordinator:
    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None
        self.last_update_success = True
    async def async_request_refresh(self):
        pass
    def async_set_updated_data(self, data):
        self.data = data

class _UpdateFailed(Exception):
    pass


# =============================================================
# sys.modules — Mock-hierarki
# =============================================================

mock_ha = MagicMock()
sys.modules["homeassistant"] = mock_ha
sys.modules["homeassistant.components"] = mock_ha.components
sys.modules["homeassistant.components.sensor"] = mock_ha.components.sensor
sys.modules["homeassistant.components.binary_sensor"] = mock_ha.components.binary_sensor
sys.modules["homeassistant.helpers.restore_state"] = mock_ha.helpers.restore_state
sys.modules["homeassistant.config_entries"] = mock_ha.config_entries
sys.modules["homeassistant.core"] = mock_ha.core
sys.modules["homeassistant.exceptions"] = mock_ha.exceptions
sys.modules["homeassistant.helpers"] = mock_ha.helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha.helpers.aiohttp_client
sys.modules["homeassistant.helpers.entity_platform"] = mock_ha.helpers.entity_platform
sys.modules["homeassistant.helpers.event"] = mock_ha.helpers.event
sys.modules["homeassistant.helpers.update_coordinator"] = mock_ha.helpers.update_coordinator
sys.modules["homeassistant.helpers.storage"] = mock_ha.helpers.storage
sys.modules["homeassistant.util"] = mock_ha.util
sys.modules["homeassistant.util.dt"] = mock_ha.util.dt

mock_ha.components.sensor.SensorEntity = _SensorEntity
mock_ha.components.sensor.SensorDeviceClass = MagicMock()
mock_ha.components.binary_sensor.BinarySensorEntity = _BinarySensorEntity
mock_ha.helpers.restore_state.RestoreEntity = _RestoreEntity
mock_ha.helpers.update_coordinator.CoordinatorEntity = _CoordinatorEntity
mock_ha.helpers.update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
mock_ha.helpers.update_coordinator.UpdateFailed = _UpdateFailed
mock_ha.helpers.storage.Store = MagicMock()

mock_ha.util.dt.parse_datetime = isoparse
mock_ha.util.dt.now = lambda: datetime.now(timezone.utc)

sys.modules["aiohttp"] = MagicMock()


# =============================================================
# Ladda integrationsmoduler (en gång)
# =============================================================

integration_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../custom_components/tibber-extended")
)
if integration_path not in sys.path:
    sys.path.insert(0, integration_path)

import const as _const  # noqa: E402
import utils as _utils  # noqa: E402

_te = types.ModuleType("tibber_extended")
_te.const = _const
_te.utils = _utils
sys.modules["tibber_extended"] = _te
sys.modules["tibber_extended.const"] = _const
sys.modules["tibber_extended.utils"] = _utils


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(integration_path, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load_module("tibber_extended.sensor", "sensor.py")
_load_module("tibber_extended.binary_sensor", "binary_sensor.py")
