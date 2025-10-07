"""Tests for Tibber Extended config flow."""
import pytest
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.tibber_extended.config_flow import TibberExtendedConfigFlow
from custom_components.tibber_extended.const import DOMAIN


@pytest.mark.asyncio
async def test_form_user(hass: HomeAssistant):
    """Test user form."""
    flow = TibberExtendedConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_user()
    
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_form_valid_token(hass: HomeAssistant):
    """Test form with valid token."""
    flow = TibberExtendedConfigFlow()
    flow.hass = hass
    
    mock_response = {"data": {"viewer": {"homes": [{"id": "test"}]}}}
    
    with patch.object(flow, "_validate_token", return_value=True):
        result = await flow.async_step_user({
            "access_token": "test-token",
            "home_name": "Test Home",
            "resolution": "QUARTER_HOURLY",
            "update_times": "13:00, 15:00"
        })
    
    assert result["type"] == "create_entry"
    assert result["title"] == "Test Home"


@pytest.mark.asyncio
async def test_form_invalid_token(hass: HomeAssistant):
    """Test form with invalid token."""
    flow = TibberExtendedConfigFlow()
    flow.hass = hass
    
    with patch.object(flow, "_validate_token", return_value=False):
        result = await flow.async_step_user({
            "access_token": "invalid-token",
            "home_name": "Test Home",
            "resolution": "QUARTER_HOURLY",
            "update_times": "13:00, 15:00"
        })
    
    assert result["type"] == "form"
    assert "invalid_token" in result["errors"]["base"]


@pytest.mark.asyncio
async def test_form_invalid_time_format(hass: HomeAssistant):
    """Test form with invalid time format."""
    flow = TibberExtendedConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_user({
        "access_token": "",
        "home_name": "Test Home",
        "resolution": "QUARTER_HOURLY",
        "update_times": "25:00, abc"  # Invalid
    })
    
    assert result["type"] == "form"
    assert "invalid_time_format" in result["errors"]["base"]
