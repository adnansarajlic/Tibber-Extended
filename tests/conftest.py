"""Fixtures for Tibber Extended tests."""
import pytest
from unittest.mock import Mock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.tibber_extended.const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_HOME_NAME,
    CONF_RESOLUTION,
    CONF_UPDATE_TIMES,
    DEFAULT_DEMO_TOKEN,
)


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Home",
        data={
            CONF_ACCESS_TOKEN: DEFAULT_DEMO_TOKEN,
            CONF_HOME_NAME: "Test Home",
            CONF_RESOLUTION: "QUARTER_HOURLY",
            CONF_UPDATE_TIMES: ["13:00", "15:00"],
        },
        source="user",
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_tibber_data():
    """Mock Tibber API response."""
    return {
        "data": {
            "viewer": {
                "homes": [
                    {
                        "id": "test-home-id",
                        "appNickname": "Test Home",
                        "currentSubscription": {
                            "priceInfo": {
                                "today": [
                                    {
                                        "total": 0.0956,
                                        "startsAt": "2025-10-06T00:00:00.000+02:00",
                                        "level": "VERY_CHEAP"
                                    },
                                    {
                                        "total": 0.0954,
                                        "startsAt": "2025-10-06T00:15:00.000+02:00",
                                        "level": "VERY_CHEAP"
                                    }
                                ],
                                "tomorrow": [
                                    {
                                        "total": 0.1056,
                                        "startsAt": "2025-10-07T00:00:00.000+02:00",
                                        "level": "CHEAP"
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
    }
