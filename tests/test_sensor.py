"""Tests for Tibber Extended sensor."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.tibber_extended.sensor import (
    TibberDataCoordinator,
    TibberPriceSensor,
    async_setup_entry,
)
from custom_components.tibber_extended.const import TIBBER_API_URL


@pytest.mark.asyncio
async def test_coordinator_fetch_success(hass: HomeAssistant, mock_config_entry, mock_tibber_data):
    """Test successful data fetch."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_tibber_data)
        mock_post.return_value.__aenter__.return_value = mock_response
        
        await coordinator._async_update_data()
        
        assert coordinator.data is not None
        assert "test-home-id" in coordinator.data
        assert len(coordinator.data["test-home-id"]["today"]) == 2
        assert len(coordinator.data["test-home-id"]["tomorrow"]) == 1


@pytest.mark.asyncio
async def test_coordinator_fetch_api_error(hass: HomeAssistant, mock_config_entry):
    """Test API error handling."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_fetch_graphql_error(hass: HomeAssistant, mock_config_entry):
    """Test GraphQL error handling."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    
    error_response = {
        "errors": [{"message": "Unauthorized"}]
    }
    
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=error_response)
        mock_post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_sensor_creation(hass: HomeAssistant, mock_config_entry, mock_tibber_data):
    """Test sensor creation."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    coordinator.data = {
        "test-home-id": {
            "name": "Test Home",
            "today": mock_tibber_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"],
            "tomorrow": []
        }
    }
    
    sensor = TibberPriceSensor(coordinator, "test-home-id", "Test Home")
    
    assert sensor.name == "Test Home Electricity Price"
    assert sensor.unique_id == "test-home-id_electricity_price"
    assert sensor.native_unit_of_measurement == "kr/kWh"


@pytest.mark.asyncio
async def test_sensor_current_price(hass: HomeAssistant, mock_config_entry, mock_tibber_data):
    """Test current price calculation."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    
    # Mock current time to match first price point
    test_time = dt_util.parse_datetime("2025-10-06T00:05:00.000+02:00")
    
    coordinator.data = {
        "test-home-id": {
            "name": "Test Home",
            "today": mock_tibber_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"],
            "tomorrow": []
        }
    }
    
    sensor = TibberPriceSensor(coordinator, "test-home-id", "Test Home")
    
    with patch("homeassistant.util.dt.now", return_value=test_time):
        price = sensor.native_value
        assert price == 0.0956


@pytest.mark.asyncio
async def test_sensor_attributes(hass: HomeAssistant, mock_config_entry, mock_tibber_data):
    """Test sensor attributes."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    coordinator.data = {
        "test-home-id": {
            "name": "Test Home",
            "today": mock_tibber_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"],
            "tomorrow": mock_tibber_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["tomorrow"]
        }
    }
    coordinator.last_update_success = True
    
    sensor = TibberPriceSensor(coordinator, "test-home-id", "Test Home")
    
    attrs = sensor.extra_state_attributes
    
    assert "today" in attrs
    assert "tomorrow" in attrs
    assert attrs["today"]["count"] == 2
    assert attrs["tomorrow"]["count"] == 1
    assert "min" in attrs["today"]
    assert "max" in attrs["today"]
    assert "avg" in attrs["today"]


@pytest.mark.asyncio
async def test_sensor_icon_changes(hass: HomeAssistant, mock_config_entry, mock_tibber_data):
    """Test icon changes based on price level."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    
    test_time = dt_util.parse_datetime("2025-10-06T00:05:00.000+02:00")
    
    coordinator.data = {
        "test-home-id": {
            "name": "Test Home",
            "today": mock_tibber_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]["today"],
            "tomorrow": []
        }
    }
    coordinator.last_update_success = True
    
    sensor = TibberPriceSensor(coordinator, "test-home-id", "Test Home")
    
    with patch("homeassistant.util.dt.now", return_value=test_time):
        icon = sensor.icon
        # First price point is VERY_CHEAP
        assert icon == "mdi:arrow-down-bold"


@pytest.mark.asyncio
async def test_sensor_availability(hass: HomeAssistant, mock_config_entry):
    """Test sensor availability."""
    coordinator = TibberDataCoordinator(hass, mock_config_entry)
    sensor = TibberPriceSensor(coordinator, "test-home-id", "Test Home")
    
    # No data
    coordinator.data = None
    coordinator.last_update_success = False
    assert sensor.available is False
    
    # With data
    coordinator.data = {"test-home-id": {"name": "Test", "today": [], "tomorrow": []}}
    coordinator.last_update_success = True
    assert sensor.available is True
