"""
Tester för koordinatorn (TibberDataCoordinator).

Täcker: schemaläggning, smart caching, midnight shift,
        persistent storage och API-retry/felhantering.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from tibber_extended.sensor import TibberDataCoordinator


class TestScheduling:
    """Tester för koordinatorns schemaläggning."""

    @pytest.mark.asyncio
    async def test_schedules_hardcoded_times(self):
        """Verifiera att koordinatorn schemalägger 13, 14 och 15."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}

        with patch("tibber_extended.sensor.async_track_time_change") as m_track:
            TibberDataCoordinator(mock_hass, mock_entry)
            assert m_track.call_count == 4

            scheduled_hours = [
                call.kwargs.get("hour")
                for call in m_track.call_args_list
                if "hour" in call.kwargs
            ]
            assert 13 in scheduled_hours
            assert 14 in scheduled_hours
            assert 15 in scheduled_hours


class TestSmartCaching:
    """Tester för koordinatorns cachnings-logik."""

    @pytest.mark.asyncio
    async def test_skips_api_when_data_exists(self):
        """Ska hoppa över API-anrop om data redan finns."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass

        with patch.object(coordinator, "_now_in_home_tz") as m_now, \
             patch.object(coordinator, "async_save_to_storage", new_callable=AsyncMock):
            m_now.return_value = datetime(2024, 1, 1, 10, 0)
            coordinator.data = {"h1": {"today": [{"total": 1, "startsAt": "2024-01-01T10:00:00Z"}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                await coordinator._async_update_data()
                m_sess.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_when_tomorrow_missing_after_1245(self):
        """Måste hämta data om det är efter 12:45 och imorgon saknas."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass

        with patch.object(coordinator, "_now_in_home_tz") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 13, 0)
            coordinator.data = {"h1": {"today": [{"total": 1, "startsAt": "2024-01-01T10:00:00Z"}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                try:
                    await coordinator._async_update_data()
                except Exception:
                    pass
                m_sess.assert_called()

    @pytest.mark.asyncio
    async def test_force_update_bypasses_cache(self):
        """Force update ska trigga API-anrop även om data finns."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.hass = mock_hass
        coordinator._force_update = True

        with patch.object(coordinator, "_now_in_home_tz") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 0)
            coordinator.data = {"h1": {"today": [{"total": 1, "startsAt": "2024-01-01T10:00:00Z"}], "tomorrow": []}}

            with patch("tibber_extended.sensor.async_get_clientsession") as m_sess:
                try:
                    await coordinator._async_update_data()
                except Exception:
                    pass
                m_sess.assert_called()


class TestMidnightShift:
    """Tester för midnatts-skiftet (tomorrow → today)."""

    @pytest.mark.asyncio
    async def test_shifts_tomorrow_to_today(self):
        """Midnattslogiken ska flytta tomorrow → today."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = {"h1": {"today": [1], "tomorrow": [2]}}

        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2024, 1, 2).date()

        with patch.object(coordinator, "_async_update_data", new_callable=AsyncMock), \
             patch("tibber_extended.sensor.asyncio.sleep", new_callable=AsyncMock), \
             patch.object(coordinator, "async_save_to_storage", new_callable=AsyncMock):
            await coordinator._handle_midnight_shift(mock_now)
            assert coordinator.data["h1"]["today"] == [2]
            assert coordinator.data["h1"]["tomorrow"] == []

    @pytest.mark.asyncio
    async def test_idempotent_same_day(self):
        """Dubbelanrop av midnight shift samma dag ska inte göra något."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = {"h1": {"today": [1], "tomorrow": [2]}}

        mock_now = MagicMock()
        target_date = datetime(2024, 1, 2).date()
        mock_now.date.return_value = target_date

        with patch.object(coordinator, "_async_update_data", new_callable=AsyncMock), \
             patch("tibber_extended.sensor.asyncio.sleep", new_callable=AsyncMock), \
             patch.object(coordinator, "async_save_to_storage", new_callable=AsyncMock):
            # Första anropet
            await coordinator._handle_midnight_shift(mock_now)
            assert coordinator.data["h1"]["today"] == [2]

            # Ändra today så vi kan verifiera att andra anropet INTE skriver över
            coordinator.data["h1"]["today"] = [99]
            await coordinator._handle_midnight_shift(mock_now)
            # Ska fortfarande vara [99], inte [2] igen (tom tomorrow)
            assert coordinator.data["h1"]["today"] == [99]

    @pytest.mark.asyncio
    async def test_no_data_logs_warning(self):
        """Midnight shift utan data ska inte krascha."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = None

        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2024, 1, 2).date()

        # Ska inte krascha
        await coordinator._handle_midnight_shift(mock_now)


class TestPersistentStorage:
    """Tester för persistent lagring (Store)."""

    @pytest.mark.asyncio
    async def test_load_from_storage(self):
        """Data ska laddas korrekt från .storage vid start."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)

        cached_data = {"h1": {"today": [{"total": 0.5}], "tomorrow": []}}
        coordinator._store.async_load = AsyncMock(return_value=cached_data)

        await coordinator.async_load_from_storage()
        assert coordinator.data == cached_data

    @pytest.mark.asyncio
    async def test_save_to_storage(self):
        """async_save ska anropas med aktuell data."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)
        coordinator.data = {"h1": {"today": [1]}}

        coordinator._store.async_save = AsyncMock()
        await coordinator.async_save_to_storage()
        coordinator._store.async_save.assert_called_once_with(coordinator.data)

    @pytest.mark.asyncio
    async def test_storage_failure_graceful(self):
        """Storage-fel ska loggas men inte krascha."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)

        coordinator._store.async_load = AsyncMock(side_effect=Exception("disk error"))
        # Ska inte krascha
        await coordinator.async_load_from_storage()
        assert coordinator.data is None

    @pytest.mark.asyncio
    async def test_load_empty_storage(self):
        """Om storage är Tom ska data förbli None."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"access_token": "test", "currency": "SEK"}
        coordinator = TibberDataCoordinator(mock_hass, mock_entry)

        coordinator._store.async_load = AsyncMock(return_value=None)
        await coordinator.async_load_from_storage()
        assert coordinator.data is None
