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
    @property
    def native_unit_of_measurement(self):
        return getattr(self, "_attr_native_unit_of_measurement", None)

class _BinarySensorEntity:
    @property
    def name(self):
        return getattr(self, "_attr_name", None)

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

import const as mock_const  # noqa: E402
import utils as mock_utils  # noqa: E402

te = types.ModuleType("tibber_extended")
te.const = mock_const
te.utils = mock_utils
sys.modules["tibber_extended"] = te
sys.modules["tibber_extended.const"] = mock_const
sys.modules["tibber_extended.utils"] = mock_utils

import importlib.util  # noqa: E402

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

from tibber_extended.sensor import (  # noqa: E402
    TibberDataCoordinator,
    TibberDetailsSensor,
    TibberEnergyConsumptionSensor,
    TibberCostConsumptionSensor,
)
from tibber_extended.binary_sensor import TibberThresholdBinarySensor  # noqa: E402


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

    def test_consumption_sensors(self, mock_coordinator):
        """Energi- och kostnadssensorer ska summera rätt värden för jan."""
        energy_sensor = TibberEnergyConsumptionSensor(mock_coordinator, "h1", "Test Hem")
        cost_sensor = TibberCostConsumptionSensor(mock_coordinator, "h1", "Test Hem")
        mock_coordinator.last_update_success = True

        assert energy_sensor.native_value == 10.0
        assert cost_sensor.native_value == 20.0
        assert cost_sensor.native_unit_of_measurement == "SEK"

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
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
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
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass

        with patch.object(coordinator, "_now_in_home_tz") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 0)
            coordinator.data = {"h1": {"today": [{"total": 1}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                await coordinator._async_update_data()
                m_sess.assert_not_called()

    @pytest.mark.asyncio
    async def test_coordinator_schedules_hardcoded_times(self):
        """Verifiera att koordinatorn schemalägger 13, 14 och 15."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}

        with patch("tibber_extended.sensor.async_track_time_change") as m_track:
            TibberDataCoordinator(mock_hass, mock_entry)
            # Vi förväntar oss 3 anrop för tiderna, plus 1 för midnattsskiftet = 4 totalt
            assert m_track.call_count == 4

            # Kolla specifika timmar för ordinarie uppdateringar
            scheduled_hours = [call.kwargs.get("hour") for call in m_track.call_args_list if "hour" in call.kwargs]
            assert 13 in scheduled_hours
            assert 14 in scheduled_hours
            assert 15 in scheduled_hours

    @pytest.mark.asyncio
    async def test_smart_caching_fetches_when_tomorrow_missing_after_1245(self):
        """Måste hämta data om det är efter 12:45 och imorgon saknas."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass

        with patch.object(coordinator, "_now_in_home_tz") as m_now:
            # Klockan är 13:00 (efter 12:45)
            m_now.return_value = datetime(2024, 1, 1, 13, 0)
            # Vi har bara data för idag
            coordinator.data = {"h1": {"today": [{"total": 1}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                # Detta bör trigga ett API-anrop (inte cacha)
                try:
                    await coordinator._async_update_data()
                except Exception:
                    pass  # Vi bryr oss bara om anropet skedde
                m_sess.assert_called()

    @pytest.mark.asyncio
    async def test_multi_span_binary_sensors(self):
        """Verifiera att flera spans skapar flera sensorer."""
        from tibber_extended.binary_sensor import async_setup_entry as setup_binary

        mock_hass = MagicMock()
        mock_entry = MagicMock()
        # Två spans: 1h och 3h
        mock_entry.options = {"best_price_spans": "1, 3"}
        mock_entry.data = {"home_name": "Test"}

        mock_coordinator = MagicMock()
        mock_coordinator.data = {"h1": {}}
        mock_hass.data = {"tibber_extended": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}

        async_add_entities = MagicMock()
        await setup_binary(mock_hass, mock_entry, async_add_entities)

        # Vi förväntar oss: best_1h, best_3h, peak, threshold = 4 sensorer totalt
        added_entities = async_add_entities.call_args[0][0]
        assert len(added_entities) == 4

        names = [e.name for e in added_entities]
        assert "Test Best Price 1.0h" in names
        assert "Test Best Price 3.0h" in names
        assert "Test Peak Price" in names

    @pytest.mark.asyncio
    async def test_orphaned_sensor_cleanup(self):
        """Verifiera att gamla Best Price-sensorer städas bort om de tas bort från config."""
        from tibber_extended.binary_sensor import async_setup_entry as setup_binary

        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        # Byt från 1, 3 till bara 3
        mock_entry.options = {"best_price_spans": "3"}
        mock_entry.data = {"home_name": "Test"}

        mock_coordinator = MagicMock()
        mock_coordinator.data = {"h1": {}}
        mock_hass.data = {"tibber_extended": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}

        # Mocka entity_registry functions
        mock_ent_reg = MagicMock()
        # En gammal sensor som fanns i registry för 1h
        old_entity = MagicMock()
        old_entity.entity_id = "binary_sensor.test_best_price_1_0h"
        old_entity.unique_id = "tibber_extended_h1_best_1.0h_price"
        old_entity.domain = "binary_sensor"

        # Tibber Price Sensor i registry för att se att den inte tas bort
        price_entity = MagicMock()
        price_entity.entity_id = "sensor.test_price"
        price_entity.unique_id = "tibber_extended_h1_electricity_price"
        price_entity.domain = "sensor"

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_ent_reg), \
             patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry",
                   return_value=[old_entity, price_entity]):
            async_add_entities = MagicMock()
            await setup_binary(mock_hass, mock_entry, async_add_entities)

        # Verifiera att async_remove anropades för 1h-sensorn
        mock_ent_reg.async_remove.assert_called_with("binary_sensor.test_best_price_1_0h")
        # Prissensorn ska vara kvar
        assert mock_ent_reg.async_remove.call_count == 1

    @pytest.mark.asyncio
    async def test_per_span_time_restriction(self):
        """Verifiera att span-specifik restriktion prioriteras över global."""
        from tibber_extended.binary_sensor import async_setup_entry as setup_binary

        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        # 1h använder global (20-06), 3h använder specifik (10-14)
        mock_entry.options = {
            "best_price_spans": "1, 3[10:00-14:00]",
            "restrict_time_start": "20:00",
            "restrict_time_end": "06:00"
        }
        mock_entry.data = {"home_name": "Test"}

        mock_coordinator = MagicMock()
        mock_coordinator.data = {"h1": {}}
        mock_coordinator.entry = mock_entry
        mock_hass.data = {"tibber_extended": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}

        async_add_entities = MagicMock()
        with patch("homeassistant.helpers.entity_registry.async_get"):
            await setup_binary(mock_hass, mock_entry, async_add_entities)

        added_entities = async_add_entities.call_args[0][0]

        # Hitta 1h och 3h sensorerna
        s_1h = next(e for e in added_entities if "1.0h" in e.name)
        s_3h = next(e for e in added_entities if "3.0h" in e.name)

        # 1h ska ha globala tider
        assert s_1h.restrict_start == "20:00"
        assert s_1h.restrict_end == "06:00"

        # 3h ska ha de specifika tiderna i fältet
        assert s_3h.restrict_start == "10:00"
        assert s_3h.restrict_end == "14:00"





class TestAvailability:
    """Tester för sensorernas tillgänglighetslogik."""

    def test_sensors_unavailable_when_no_data(self):
        """Sensorer ska vara unavailable om koordinatorn saknar data för hemmet."""
        coordinator = MagicMock()
        coordinator.data = {} # Ingen data alls
        coordinator.last_update_success = True

        # Vi behöver importera TibberPriceSensor om den inte finns i sys.modules
        from tibber_extended.sensor import TibberPriceSensor

        price_sensor = TibberPriceSensor(coordinator, "h1", "Test", "SEK")
        energy_sensor = TibberEnergyConsumptionSensor(coordinator, "h1", "Test")

        assert price_sensor.available is False
        assert energy_sensor.available is False

    def test_sensors_available_when_data_exists(self):
        coordinator = MagicMock()
        coordinator.data = {"h1": {"today": [1]}}
        coordinator.last_update_success = True

        from tibber_extended.sensor import TibberPriceSensor
        price_sensor = TibberPriceSensor(coordinator, "h1", "Test", "SEK")
        assert price_sensor.available is True


if __name__ == "__main__":
    pytest.main([__file__])
