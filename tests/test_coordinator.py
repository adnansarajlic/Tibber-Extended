"""
Sammanställda tester för Tibber Extended integrationen.

Strategi:
- Använder MagicMock() som HA-moduler (auto-skapar attribut vid åtkomst).
- UNDANTAG: SensorEntity, BinarySensorEntity, CoordinatorEntity,
  DataUpdateCoordinator och UpdateFailed måste vara riktiga klasser,
  annars får vi metaclass-konflikter vid arv.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import sys
import os
import types
from dateutil.parser import isoparse


# --- Riktiga stub-klasser för arv ---
class _SensorEntity:
    pass

class _BinarySensorEntity:
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


# --- Bygg mock-hierarkin ---
mock_ha = MagicMock()
sys.modules["homeassistant"] = mock_ha
sys.modules["homeassistant.components"] = mock_ha.components
sys.modules["homeassistant.components.sensor"] = mock_ha.components.sensor
sys.modules["homeassistant.components.binary_sensor"] = mock_ha.components.binary_sensor
sys.modules["homeassistant.config_entries"] = mock_ha.config_entries
sys.modules["homeassistant.core"] = mock_ha.core
sys.modules["homeassistant.exceptions"] = mock_ha.exceptions
sys.modules["homeassistant.helpers"] = mock_ha.helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha.helpers.aiohttp_client
sys.modules["homeassistant.helpers.entity_platform"] = mock_ha.helpers.entity_platform
sys.modules["homeassistant.helpers.event"] = mock_ha.helpers.event
sys.modules["homeassistant.helpers.update_coordinator"] = mock_ha.helpers.update_coordinator
sys.modules["homeassistant.util"] = mock_ha.util
sys.modules["homeassistant.util.dt"] = mock_ha.util.dt

# Sätt riktiga klasser så att arv fungerar
mock_ha.components.sensor.SensorEntity = _SensorEntity
mock_ha.components.binary_sensor.BinarySensorEntity = _BinarySensorEntity
mock_ha.helpers.update_coordinator.CoordinatorEntity = _CoordinatorEntity
mock_ha.helpers.update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
mock_ha.helpers.update_coordinator.UpdateFailed = _UpdateFailed

# Konfigurera dt_util med riktiga funktioner
mock_ha.util.dt.parse_datetime = isoparse
mock_ha.util.dt.now = lambda: datetime.now(timezone.utc)

# Mocka aiohttp
sys.modules["aiohttp"] = MagicMock()


# --- Fixa relativa importer ---
integration_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../custom_components/tibber-extended")
)
if integration_path not in sys.path:
    sys.path.insert(0, integration_path)

import const as mock_const
import utils as mock_utils

te = types.ModuleType("tibber_extended")
te.const = mock_const
te.utils = mock_utils
sys.modules["tibber_extended"] = te
sys.modules["tibber_extended.const"] = mock_const
sys.modules["tibber_extended.utils"] = mock_utils

import importlib.util

spec_sensor = importlib.util.spec_from_file_location(
    "tibber_extended.sensor", os.path.join(integration_path, "sensor.py")
)
sensor_mod = importlib.util.module_from_spec(spec_sensor)
sys.modules["tibber_extended.sensor"] = sensor_mod
spec_sensor.loader.exec_module(sensor_mod)

spec_binary = importlib.util.spec_from_file_location(
    "tibber_extended.binary_sensor", os.path.join(integration_path, "binary_sensor.py")
)
binary_mod = importlib.util.module_from_spec(spec_binary)
sys.modules["tibber_extended.binary_sensor"] = binary_mod
spec_binary.loader.exec_module(binary_mod)

from tibber_extended.sensor import (
    TibberDataCoordinator,
    TibberDetailsSensor,
    TibberConsumptionSensor,
)
from tibber_extended.binary_sensor import TibberThresholdBinarySensor


# =============================================================
# TESTER
# =============================================================

class TestSensors:
    """Tester för sensorer: trösklar, elnätsbolag, månadsförbrukning."""

    @pytest.fixture
    def mock_coordinator(self):
        coordinator = MagicMock()
        coordinator.data = {
            "h1": {
                "today": [
                    {"total": 0.4, "startsAt": "2024-01-01T10:00:00Z"},
                    {"total": 0.6, "startsAt": "2024-01-01T11:00:00Z"},
                ],
                "metadata": {"grid_company": "E.ON"},
                "consumption": [
                    {"from": "2023-12-31T23:00:00Z", "consumption": 10.0, "cost": 20.0},
                    {"from": "2024-01-01T10:00:00Z", "consumption": 5.0, "cost": 10.0},
                    {"from": "2024-01-02T10:00:00Z", "consumption": 5.0, "cost": 10.0},
                ],
            }
        }
        coordinator._home_timezones = {"h1": "UTC"}
        coordinator.entry.options = {}
        coordinator.entry.data = {"price_threshold": 0.5, "currency": "SEK"}
        coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 15, tzinfo=timezone.utc)
        return coordinator

    def test_threshold_binary_sensor(self, mock_coordinator):
        """Tröskel-sensorn ska vara PÅ när aktuellt pris < tröskelvärde."""
        sensor = TibberThresholdBinarySensor(mock_coordinator, "h1", "Test Hem")
        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc)
            assert sensor.is_on is True

    def test_consumption_sensor(self, mock_coordinator):
        """Månadsförbrukning ska summera kWh och kostnad för jan."""
        sensor = TibberConsumptionSensor(mock_coordinator, "h1", "Test Hem")
        mock_coordinator.last_update_success = True
        assert sensor.native_value == 10.0
        assert sensor.extra_state_attributes["monthly_cost"] == 20.0

    def test_grid_company_sensor(self, mock_coordinator):
        """Elnätsbolag-sensorn ska returnera gridCompany."""
        sensor = TibberDetailsSensor(
            mock_coordinator, "h1", "Test Hem", "grid_company", "Grid", "mdi:tower"
        )
        mock_coordinator.last_update_success = True
        assert sensor.native_value == "E.ON"


class TestCoordinatorLogic:
    """Tester för koordinatorns kärnlogik."""

    @pytest.mark.asyncio
    async def test_midnight_shift_logic(self):
        """Midnattslogiken ska flytta tomorrow → today."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK", "update_times": "13:00"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = {"h1": {"today": [1], "tomorrow": [2]}}

        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2024, 1, 2).date()

        with patch.object(coordinator, "_async_update_data", new_callable=AsyncMock), \
             patch("tibber_extended.sensor.asyncio.sleep", new_callable=AsyncMock):
            await coordinator._handle_midnight_shift(mock_now)
            assert coordinator.data["h1"]["today"] == [2]
            assert coordinator.data["h1"]["tomorrow"] == []

    @pytest.mark.asyncio
    async def test_smart_caching_skips_api(self):
        """Caching ska hoppa över API-anrop om data redan finns."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK", "update_times": "13:00"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass

        with patch.object(coordinator, "_now_in_home_tz") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 0)
            coordinator.data = {"h1": {"today": [{"total": 1}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                await coordinator._async_update_data()
                m_sess.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])
