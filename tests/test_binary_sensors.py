"""
Tester för binära sensorer (Best Price, Peak Price, Threshold).

Täcker: is_on-logik, stabilitet, RestoreEntity, setup_entry, attribut,
        tröskelvärden, per-span restriktioner, orphan-cleanup.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from tibber_extended.binary_sensor import (
    TibberTargetHoursBinarySensor,
    TibberThresholdBinarySensor,
    async_setup_entry as setup_binary,
)


@pytest.fixture
def mock_coordinator():
    """Standard coordinator med testdata."""
    coordinator = MagicMock()
    coordinator.data = {
        "h1": {
            "today": [
                {"total": 0.4, "startsAt": "2024-01-01T10:00:00Z"},
                {"total": 0.6, "startsAt": "2024-01-01T11:00:00Z"},
                {"total": 0.2, "startsAt": "2024-01-01T12:00:00Z"},
                {"total": 0.8, "startsAt": "2024-01-01T13:00:00Z"},
            ],
            "tomorrow": [],
        }
    }
    coordinator._home_timezones = {"h1": "UTC"}
    coordinator.entry.options = {}
    coordinator.entry.data = {"price_threshold": 0.5, "currency": "SEK"}
    coordinator._now_in_home_tz = lambda h: datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    coordinator._force_update = False
    coordinator.resolution = "HOURLY"
    return coordinator


# =============================================================
# TibberTargetHoursBinarySensor — is_on
# =============================================================

class TestBestPriceIsOn:
    """Tester för is_on logiken i Best Price sensorn."""

    def test_is_on_within_window(self):
        """is_on ska vara True om nuvarande tid är inom fönstret."""
        coordinator = MagicMock()
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = "2024-01-01T10:00:00+00:00"
        sensor.period_end = "2024-01-01T11:00:00+00:00"

        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
            assert sensor.is_on is True

    def test_is_on_outside_window(self):
        """is_on ska vara False utanför fönstret."""
        coordinator = MagicMock()
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = "2024-01-01T10:00:00+00:00"
        sensor.period_end = "2024-01-01T11:00:00+00:00"

        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            assert sensor.is_on is False

    def test_is_on_no_period(self):
        """is_on ska vara False om period saknas."""
        coordinator = MagicMock()
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        assert sensor.is_on is False

    def test_is_on_at_start_boundary(self):
        """is_on ska vara True exakt vid period_start."""
        coordinator = MagicMock()
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = "2024-01-01T10:00:00+00:00"
        sensor.period_end = "2024-01-01T11:00:00+00:00"

        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
            assert sensor.is_on is True

    def test_is_on_at_end_boundary(self):
        """is_on ska vara False exakt vid period_end (exklusiv)."""
        coordinator = MagicMock()
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = "2024-01-01T10:00:00+00:00"
        sensor.period_end = "2024-01-01T11:00:00+00:00"

        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            m_now.return_value = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
            assert sensor.is_on is False


# =============================================================
# TibberTargetHoursBinarySensor — _calculate_period
# =============================================================

class TestBestPriceCalculation:
    """Tester för fönsterberäkningen."""

    def test_calculate_finds_cheapest(self, mock_coordinator):
        """Ska hitta det billigaste 2h-fönstret."""
        sensor = TibberTargetHoursBinarySensor(
            mock_coordinator, "h1", "Test", "best", 2.0, "HOURLY"
        )
        sensor._calculate_period()
        # 12:00 (0.2) + 11:00 (0.6) = ...men sliding window:
        # 10+11=1.0, 11+12=0.8, 12+13=1.0 → 11:00-12:00 = 0.8
        assert sensor.period_start == "2024-01-01T11:00:00Z"
        assert sensor.avg_price is not None

    def test_calculate_no_data(self):
        """_calculate_period ska hantera tom data."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.entry.options = {}
        coordinator.entry.data = {}
        coordinator._force_update = False
        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor._calculate_period()
        assert sensor.period_start is None

    def test_calculate_quarter_hourly(self, mock_coordinator):
        """Quarter-hourly ska beräkna rätt antal slots."""
        mock_coordinator.data["h1"]["today"] = [
            {"total": 0.1 * i, "startsAt": f"2024-01-01T10:{i*15:02d}:00Z"}
            for i in range(8)  # 2 timmar à 15 min = 8 slots
        ]
        sensor = TibberTargetHoursBinarySensor(
            mock_coordinator, "h1", "Test", "best", 1.0, "QUARTER_HOURLY"
        )
        sensor._calculate_period()
        # 1h = 4 slots vid QUARTER_HOURLY
        assert sensor.period_start is not None

    def test_extra_attributes(self, mock_coordinator):
        """Attribut ska innehålla target_hours och period-fält."""
        sensor = TibberTargetHoursBinarySensor(
            mock_coordinator, "h1", "Test", "best", 2.0, "HOURLY"
        )
        sensor._calculate_period()
        attrs = sensor.extra_state_attributes
        assert attrs["target_hours"] == 2.0
        assert "period_start" in attrs
        assert "period_end" in attrs
        assert "avg_price_in_period" in attrs


# =============================================================
# Stability (RestoreEntity / framtida fönster)
# =============================================================

class TestBestPriceStability:
    """Tester för stabilitetslogiken (bevarar framtida fönster)."""

    def test_future_window_preserved(self):
        """Fönstret ska INTE ändras om det redan ligger i framtiden."""
        coordinator = MagicMock()
        coordinator.entry.options = {"restrict_time_start": "", "restrict_time_end": ""}
        coordinator.entry.data = {"restrict_time_start": "", "restrict_time_end": ""}

        now = datetime.now(timezone.utc)
        future_start = (now + timedelta(hours=5)).replace(minute=0, second=0, microsecond=0)
        future_start_iso = future_start.isoformat()

        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = future_start_iso
        sensor.period_end = (future_start + timedelta(hours=1)).isoformat()

        coordinator.data = {
            "h1": {
                "today": [
                    {"total": 10.0, "startsAt": future_start_iso},
                    {"total": 0.1, "startsAt": (now + timedelta(hours=2)).isoformat()},
                ],
                "tomorrow": []
            }
        }
        coordinator._home_timezones = {"h1": "UTC"}
        coordinator._force_update = False

        sensor._calculate_period()
        assert sensor.period_start == future_start_iso

    def test_active_window_preserved(self):
        """Fönstret ska bevaras om pågående, så att det inte hoppar i mitten av en körning."""
        coordinator = MagicMock()
        coordinator.entry.options = {"restrict_time_start": "", "restrict_time_end": ""}
        coordinator.entry.data = {"restrict_time_start": "", "restrict_time_end": ""}

        now = datetime.now(timezone.utc)
        # Sätt fönstret till att ha börjat för 30 minuter sedan och pågår 30 minuter till
        active_start = (now - timedelta(minutes=30)).replace(second=0, microsecond=0)
        active_end = (active_start + timedelta(hours=1))

        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = active_start.isoformat()
        sensor.period_end = active_end.isoformat()

        coordinator.data = {
            "h1": {
                "today": [
                    {"total": 10.0, "startsAt": active_start.isoformat()},
                    {"total": 0.1, "startsAt": (now + timedelta(hours=2)).isoformat()},
                ],
                "tomorrow": []
            }
        }
        coordinator._home_timezones = {"h1": "UTC"}
        coordinator._force_update = False

        sensor._calculate_period()
        # Stabilitetslogiken ska gälla för p_end > now, så vi stannar kvar på samma span
        assert sensor.period_start == active_start.isoformat()

    def test_force_update_overrides_stability(self):
        """Force update ska tillåta omberäkning trots framtida fönster."""
        coordinator = MagicMock()
        coordinator.entry.options = {"restrict_time_start": "", "restrict_time_end": ""}
        coordinator.entry.data = {"restrict_time_start": "", "restrict_time_end": ""}

        now = datetime.now(timezone.utc)
        future_start = (now + timedelta(hours=5)).replace(minute=0, second=0, microsecond=0)
        future_start_iso = future_start.isoformat()

        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = future_start_iso
        sensor.period_end = (future_start + timedelta(hours=1)).isoformat()

        coordinator.data = {
            "h1": {
                "today": [
                    {"total": 10.0, "startsAt": future_start_iso},
                    {"total": 0.1, "startsAt": (now + timedelta(hours=2)).isoformat()},
                ],
                "tomorrow": []
            }
        }
        coordinator._home_timezones = {"h1": "UTC"}
        coordinator._force_update = True

        sensor._calculate_period()
        assert sensor.period_start != future_start_iso

    def test_expired_window_recalculates(self):
        """Passerat fönster ska räknas om."""
        coordinator = MagicMock()
        coordinator.entry.options = {"restrict_time_start": "", "restrict_time_end": ""}
        coordinator.entry.data = {"restrict_time_start": "", "restrict_time_end": ""}

        now = datetime.now(timezone.utc)
        past_start = (now - timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
        future_slot = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        sensor = TibberTargetHoursBinarySensor(
            coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.period_start = past_start.isoformat()
        sensor.period_end = (past_start + timedelta(hours=1)).isoformat()

        coordinator.data = {
            "h1": {
                "today": [
                    {"total": 0.5, "startsAt": future_slot.isoformat()},
                ],
                "tomorrow": []
            }
        }
        coordinator._home_timezones = {"h1": "UTC"}
        coordinator._force_update = False

        sensor._calculate_period()
        # Passerat fönster → stabilitet gäller ej → omberäkning
        assert sensor.period_start == future_slot.isoformat()

    @pytest.mark.asyncio
    async def test_target_hours_registers_time_triggers(self, mock_coordinator):
        """async_added_to_hass ska registrera triggers vid tidsslag."""
        sensor = TibberTargetHoursBinarySensor(
            mock_coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.hass = MagicMock()
        sensor.async_on_remove = MagicMock()

        # Säkerställ att async_get_last_state inte krashar
        sensor.async_get_last_state = AsyncMock(return_value=None)
        sensor.async_write_ha_state = MagicMock()

        with patch("homeassistant.helpers.event.async_track_time_change") as m_track:
            await sensor.async_added_to_hass()

            # HOURLY -> ska bara registreras en minut: 0
            m_track.assert_called_once()
            kwargs = m_track.call_args.kwargs
            assert kwargs["minute"] == 0
            assert kwargs["second"] == 2

    @pytest.mark.asyncio
    async def test_target_hours_update_state(self, mock_coordinator):
        """_update_state ska anropa async_write_ha_state."""
        sensor = TibberTargetHoursBinarySensor(
            mock_coordinator, "h1", "Test", "best", 1.0, "HOURLY"
        )
        sensor.async_write_ha_state = MagicMock()
        await sensor._update_state()
        sensor.async_write_ha_state.assert_called_once()


# =============================================================
# TibberThresholdBinarySensor
# =============================================================

class TestThresholdBinarySensor:
    """Tester för tröskelvärdes-sensorn."""

    def test_is_on_below_threshold(self, mock_coordinator):
        """is_on ska vara True när priset < tröskelvärdet."""
        sensor = TibberThresholdBinarySensor(mock_coordinator, "h1", "Test")
        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            # 10:05 → pris 0.4 < tröskel 0.5 → True
            m_now.return_value = datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc)
            assert sensor.is_on is True

    def test_is_off_above_threshold(self, mock_coordinator):
        """is_on ska vara False när priset >= tröskelvärdet."""
        sensor = TibberThresholdBinarySensor(mock_coordinator, "h1", "Test")
        with patch("tibber_extended.binary_sensor.dt_util.now") as m_now:
            # 11:05 → pris 0.6 >= tröskel 0.5 → False
            m_now.return_value = datetime(2024, 1, 1, 11, 5, tzinfo=timezone.utc)
            assert sensor.is_on is False

    def test_is_off_no_data(self):
        """is_on ska vara False utan data."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.entry.options = {}
        coordinator.entry.data = {"price_threshold": 0.5}
        sensor = TibberThresholdBinarySensor(coordinator, "h1", "Test")
        assert sensor.is_on is False

    def test_extra_attributes(self, mock_coordinator):
        """Threshold-attributet ska finnas."""
        sensor = TibberThresholdBinarySensor(mock_coordinator, "h1", "Test")
        attrs = sensor.extra_state_attributes
        assert "threshold" in attrs
        assert attrs["threshold"] == 0.5


# =============================================================
# async_setup_entry
# =============================================================

class TestSetupEntry:
    """Tester för async_setup_entry och sensor-skapning."""

    @pytest.mark.asyncio
    async def test_multi_span_creates_sensors(self):
        """Flera spans ska skapa motsvarande antal sensorer."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.options = {"best_price_spans": "1, 3"}
        mock_entry.data = {"home_name": "Test"}

        mock_coordinator = MagicMock()
        mock_coordinator.data = {"h1": {}}
        mock_hass.data = {"tibber_extended": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}

        async_add_entities = MagicMock()
        await setup_binary(mock_hass, mock_entry, async_add_entities)

        added = async_add_entities.call_args[0][0]
        assert len(added) == 4  # best_1h, best_3h, peak, threshold

        names = [e.name for e in added]
        assert "Test Best Price 1.0h" in names
        assert "Test Best Price 3.0h" in names
        assert "Test Peak Price" in names

    @pytest.mark.asyncio
    async def test_orphaned_sensor_cleanup(self):
        """Gamla sensorer ska tas bort vid konfigurationsändring."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {"best_price_spans": "3"}
        mock_entry.data = {"home_name": "Test"}

        mock_coordinator = MagicMock()
        mock_coordinator.data = {"h1": {}}
        mock_hass.data = {"tibber_extended": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}

        mock_ent_reg = MagicMock()
        old_entity = MagicMock()
        old_entity.entity_id = "binary_sensor.test_best_price_1_0h"
        old_entity.unique_id = "tibber_extended_h1_best_1.0h_price"
        old_entity.domain = "binary_sensor"

        other_entity = MagicMock()
        other_entity.entity_id = "sensor.test_price"
        other_entity.unique_id = "tibber_extended_h1_electricity_price"
        other_entity.domain = "sensor"

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_ent_reg), \
             patch("homeassistant.helpers.entity_registry.async_entries_for_config_entry",
                   return_value=[old_entity, other_entity]):
            async_add_entities = MagicMock()
            await setup_binary(mock_hass, mock_entry, async_add_entities)

        mock_ent_reg.async_remove.assert_called_with("binary_sensor.test_best_price_1_0h")
        assert mock_ent_reg.async_remove.call_count == 1

    @pytest.mark.asyncio
    async def test_per_span_time_restriction(self):
        """Span-specifik restriktion ska prioriteras över global."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry"
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

        added = async_add_entities.call_args[0][0]
        s_1h = next(e for e in added if "1.0h" in e.name)
        s_3h = next(e for e in added if "3.0h" in e.name)

        assert s_1h.restrict_start == "20:00"
        assert s_1h.restrict_end == "06:00"
        assert s_3h.restrict_start == "10:00"
        assert s_3h.restrict_end == "14:00"
