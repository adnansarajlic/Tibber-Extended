"""
Tester för sensorer (Price, Consumption, Cost, Details).

Täcker: current value, availability, subunits, attribut, edge cases.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from tibber_extended.sensor import (
    TibberPriceSensor,
    TibberDetailsSensor,
    TibberEnergyConsumptionSensor,
    TibberCostConsumptionSensor,
)


@pytest.fixture
def mock_coordinator():
    """Standard coordinator med testdata för januari 2024."""
    coordinator = MagicMock()
    coordinator.data = {
        "h1": {
            "today": [
                {"total": 0.4, "energy": 0.3, "tax": 0.1, "startsAt": "2024-01-01T10:00:00Z", "level": "CHEAP"},
                {"total": 0.6, "energy": 0.45, "tax": 0.15, "startsAt": "2024-01-01T11:00:00Z", "level": "NORMAL"},
                {"total": 1.2, "energy": 0.9, "tax": 0.3, "startsAt": "2024-01-01T12:00:00Z", "level": "EXPENSIVE"},
            ],
            "tomorrow": [],
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
    coordinator.last_update_success = True
    coordinator.resolution = "HOURLY"
    return coordinator


# =============================================================
# Price Sensor
# =============================================================

class TestPriceSensor:
    """Tester för TibberPriceSensor."""

    def test_current_value(self, mock_coordinator):
        """Ska returnera korrekt pris för aktuell timme."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.native_value == 0.4

    def test_current_value_subunits(self, mock_coordinator):
        """Pris konverteras till öre korrekt."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        mock_coordinator.entry.options = {"use_subunits": True}
        mock_coordinator.entry.data = {"use_subunits": True, "currency": "SEK"}
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.native_value == 40.0

    def test_no_matching_hour_returns_none(self, mock_coordinator):
        """Returnerar None utanför prisdata."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.native_value is None

    def test_icon_cheap(self, mock_coordinator):
        """Ikon ska vara arrow-down vid CHEAP."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.icon == "mdi:arrow-down"

    def test_icon_expensive(self, mock_coordinator):
        """Ikon ska vara arrow-up vid EXPENSIVE."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.icon == "mdi:arrow-up"

    def test_icon_no_data(self, mock_coordinator):
        """Ikon ska vara mdi:flash utan data."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.icon == "mdi:flash"

    def test_extra_attributes_has_today(self, mock_coordinator):
        """Extra attribut ska innehålla today-priserna."""
        mock_coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        attrs = sensor.extra_state_attributes
        assert "today" in attrs
        assert "tomorrow" in attrs
        assert "current_level" in attrs
        assert attrs["current_level"] == "CHEAP"
        assert attrs["currency"] == "SEK"

    def test_unit_sek(self, mock_coordinator):
        """Enhet ska vara SEK/kWh."""
        sensor = TibberPriceSensor(mock_coordinator, "h1", "Test", "SEK")
        assert sensor.native_unit_of_measurement == "SEK/kWh"


# =============================================================
# Consumption Sensors
# =============================================================

class TestConsumptionSensors:
    """Tester för energi- och kostnadssensorer."""

    def test_energy_monthly_sum(self, mock_coordinator):
        """Ska summera kWh för januari."""
        sensor = TibberEnergyConsumptionSensor(mock_coordinator, "h1", "Test")
        assert sensor.native_value == 10.0  # 5.0 + 5.0 (jan)

    def test_cost_monthly_sum(self, mock_coordinator):
        """Ska summera kostnad för januari."""
        sensor = TibberCostConsumptionSensor(mock_coordinator, "h1", "Test")
        assert sensor.native_value == 20.0  # 10.0 + 10.0 (jan)

    def test_cost_unit(self, mock_coordinator):
        """Kostnadssensorn ska ha rätt enhet."""
        sensor = TibberCostConsumptionSensor(mock_coordinator, "h1", "Test")
        assert sensor.native_unit_of_measurement == "SEK"

    def test_empty_consumption(self, mock_coordinator):
        """Tom förbrukningslista ska returnera 0."""
        mock_coordinator.data["h1"]["consumption"] = []
        sensor = TibberEnergyConsumptionSensor(mock_coordinator, "h1", "Test")
        assert sensor.native_value == 0.0

    def test_cross_month_filtering(self, mock_coordinator):
        """Data från december ska inte räknas i januari."""
        # December-noden (2023-12-31) har consumption=10.0 men ska exkluderas
        # Januari-noder ska totalt ge 10.0
        sensor = TibberEnergyConsumptionSensor(mock_coordinator, "h1", "Test")
        assert sensor.native_value == 10.0

    def test_none_consumption_values(self, mock_coordinator):
        """None-värden i consumption ska hanteras som 0."""
        mock_coordinator.data["h1"]["consumption"] = [
            {"from": "2024-01-05T10:00:00Z", "consumption": None, "cost": None},
            {"from": "2024-01-06T10:00:00Z", "consumption": 3.0, "cost": 6.0},
        ]
        energy = TibberEnergyConsumptionSensor(mock_coordinator, "h1", "Test")
        cost = TibberCostConsumptionSensor(mock_coordinator, "h1", "Test")
        assert energy.native_value == 3.0
        assert cost.native_value == 6.0


# =============================================================
# Details Sensor
# =============================================================

class TestDetailsSensor:
    """Tester för diagnostik-sensorer (metadata)."""

    def test_grid_company(self, mock_coordinator):
        """Ska returnera gridCompany."""
        sensor = TibberDetailsSensor(
            mock_coordinator, "h1", "Test", "grid_company", "Grid", "mdi:tower"
        )
        assert sensor.native_value == "E.ON"

    def test_missing_key(self, mock_coordinator):
        """Icke-existerande nyckel ska returnera None."""
        sensor = TibberDetailsSensor(
            mock_coordinator, "h1", "Test", "nonexistent", "Missing", "mdi:help"
        )
        assert sensor.native_value is None


# =============================================================
# Availability
# =============================================================

class TestAvailability:
    """Tester för sensorernas tillgänglighetslogik."""

    def test_unavailable_when_no_data(self):
        """Sensorer ska vara unavailable utan data."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True

        price = TibberPriceSensor(coordinator, "h1", "Test", "SEK")
        energy = TibberEnergyConsumptionSensor(coordinator, "h1", "Test")

        assert price.available is False
        assert energy.available is False

    def test_available_with_data(self):
        """Sensorer ska vara available med data."""
        coordinator = MagicMock()
        coordinator.data = {"h1": {"today": [1]}}
        coordinator.last_update_success = True

        price = TibberPriceSensor(coordinator, "h1", "Test", "SEK")
        assert price.available is True

    def test_unavailable_on_failed_update(self):
        """Sensorer ska vara unavailable om senaste uppdateringen misslyckades."""
        coordinator = MagicMock()
        coordinator.data = {"h1": {"today": [1]}}
        coordinator.last_update_success = False

        price = TibberPriceSensor(coordinator, "h1", "Test", "SEK")
        assert price.available is False
