import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, time, timedelta
import asyncio
import sys
import os
import types

# 1. FIXA MOCKNING AV HOME ASSISTANT KLASSER
class MockBase: pass
class MockEntity(MockBase): pass
class MockCoordinatorEntity(MockEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
class MockDataUpdateCoordinator(MockBase):
    def __init__(self, hass, logger, **kwargs):
        self.hass = hass
        self.logger = logger
        self.data = None
        self.last_update_success = True
    def async_set_updated_data(self, data):
        self.data = data

# Skapa moduler
mock_ha = MagicMock()
sys.modules["homeassistant"] = mock_ha
sys.modules["aiohttp"] = MagicMock()  # Lägg till mock för aiohttp
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
sys.modules["homeassistant.components.sensor"].SensorEntity = MockEntity
sys.modules["homeassistant.components.sensor"].SensorDeviceClass = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = MockDataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception
sys.modules["homeassistant.helpers.event"] = MagicMock()
sys.modules["homeassistant.helpers.aiohttp_client"] = MagicMock()
sys.modules["homeassistant.util"] = MagicMock()
sys.modules["homeassistant.util.dt"] = MagicMock()

# 2. FIXA RELATIVA IMPORTER
integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../custom_components/tibber-extended"))
sys.path.insert(0, integration_path)

import const as mock_const
import utils as mock_utils
sys.modules["tibber_extended"] = types.ModuleType("tibber_extended")
sys.modules["tibber_extended.const"] = mock_const
sys.modules["tibber_extended.utils"] = mock_utils

import importlib.util
spec = importlib.util.spec_from_file_location("tibber_extended.sensor", os.path.join(integration_path, "sensor.py"))
sensor_mod = importlib.util.module_from_spec(spec)
sys.modules["tibber_extended.sensor"] = sensor_mod
spec.loader.exec_module(sensor_mod)

from tibber_extended.sensor import TibberDataCoordinator

class TestCoordinatorLogic:
    """Tester för logiken i TibberDataCoordinator."""

    @pytest.fixture
    def mock_hass(self): return MagicMock()

    @pytest.fixture
    def mock_entry(self):
        entry = MagicMock()
        entry.data = {"access_token": "abc", "resolution": "HOURLY", "update_times": []}
        entry.entry_id = "test"
        entry.options = {}
        return entry

    @pytest.mark.asyncio
    async def test_midnight_shift_logic(self, mock_hass, mock_entry):
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = {"h1": {"today": [1], "tomorrow": [2]}}
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2024, 1, 2).date()
        await coordinator._handle_midnight_shift(mock_now)
        assert coordinator.data["h1"]["today"] == [2]
        assert coordinator.data["h1"]["tomorrow"] == []

    @pytest.mark.asyncio
    async def test_smart_caching_skips_api(self, mock_hass, mock_entry):
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass
        with patch("tibber_extended.sensor.dt_util.now") as m_now:
            m_now.return_value.time.return_value = time(10, 0)
            coordinator.data = {"h1": {"today": [{"total": 1}], "tomorrow": []}}
            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                res = await coordinator._async_update_data()
                m_sess.assert_not_called()
                assert res == coordinator.data

    @pytest.mark.asyncio
    async def test_force_update_bypasses_cache(self, mock_hass, mock_entry):
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass
        coordinator._force_update = True
        coordinator.data = {"h1": {"today": [{"total": 1}], "tomorrow": []}}
        
        with patch("tibber_extended.sensor.dt_util.now") as m_now:
            m_now.return_value.time.return_value = time(14, 0)
            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value={"data": {"viewer": {"homes": []}}})
                m_sess.return_value.post.return_value.__aenter__.return_value = mock_resp
                await coordinator._async_update_data()
                assert m_sess.return_value.post.called is True
                assert coordinator._force_update is False

if __name__ == "__main__":
    pytest.main([__file__])
