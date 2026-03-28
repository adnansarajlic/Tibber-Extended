import pytest
import sys
import os

# Lägg till källkoden i path för att kunna importera utils trots bindestreck i mappen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../custom_components/tibber-extended")))

from utils import (
    find_best_window, 
    format_price_value, 
    validate_time_format, 
    get_unit_label, 
    parse_spans
)


# ============================================================
# parse_spans
# ============================================================

class TestParseSpans:
    """Tests for Best Price span config parsing with individual windows."""

    def test_basic_spans(self):
        assert parse_spans("1, 3, 6") == [(1.0, None, None), (3.0, None, None), (6.0, None, None)]

    def test_spans_with_restrictions(self):
        assert parse_spans("1[22:00-06:00], 3") == [(1.0, "22:00", "06:00"), (3.0, None, None)]
        assert parse_spans("1, 3[00:00-04:00], 6[10:00-20:00]") == [
            (1.0, None, None), 
            (3.0, "00:00", "04:00"), 
            (6.0, "10:00", "20:00")
        ]

    def test_float_spans(self):
        assert parse_spans("0.5, 1.5[12:00-14:00]") == [(0.5, None, None), (1.5, "12:00", "14:00")]

    def test_invalid_formats_log_warning(self):
        # Should skip invalid items but keep valid ones
        assert parse_spans("1, invalid, 3[abc-def], 6") == [(1.0, None, None), (6.0, None, None)]

    def test_empty_string(self):
        assert parse_spans("") == []
        assert parse_spans(None) == []



# ============================================================
# format_price_value
# ============================================================

class TestFormatPriceValue:
    """Tests for price formatting and unit scaling."""

    def test_kr_to_kr(self):
        """Default mode keeps values in kr/EUR."""
        assert format_price_value(0.5, False) == 0.5
        assert format_price_value(1.23456, False) == 1.2346

    def test_kr_to_ore(self):
        """Subunit mode multiplies by 100."""
        assert format_price_value(0.5, True) == 50.0
        assert format_price_value(1.23456, True) == 123.46

    def test_none_returns_none(self):
        assert format_price_value(None, True) is None
        assert format_price_value(None, False) is None

    def test_zero(self):
        assert format_price_value(0, True) == 0
        assert format_price_value(0, False) == 0

    def test_negative_price(self):
        """Negative prices occur in reality (e.g. Denmark/Germany)."""
        assert format_price_value(-0.5, False) == -0.5
        assert format_price_value(-0.5, True) == -50.0

    def test_very_large_price(self):
        """Very high prices should still format correctly."""
        assert format_price_value(99.9999, False) == 99.9999
        assert format_price_value(99.9999, True) == 9999.99


# ============================================================
# find_best_window — Basic
# ============================================================

class TestFindBestWindowBasic:
    """Core sliding window logic."""

    def test_cheapest_2h_window(self):
        prices = [
            {"total": 1.0, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": 0.2, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 0.8, "startsAt": "2024-01-01T03:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY")
        assert idx == 1
        assert val == pytest.approx(0.7)

    def test_most_expensive_2h_window(self):
        prices = [
            {"total": 1.0, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": 0.2, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 0.8, "startsAt": "2024-01-01T03:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "peak", "HOURLY")
        assert idx == 0
        assert val == pytest.approx(1.5)

    def test_identical_prices_picks_earliest(self):
        prices = [
            {"total": 0.5, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T03:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY")
        assert idx == 0
        assert val == pytest.approx(1.0)

    def test_single_slot(self):
        """When target is 1 hour, should pick cheapest single slot."""
        prices = [
            {"total": 0.8, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.2, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T02:00:00Z"},
        ]
        idx, val = find_best_window(prices, 1, "best", "HOURLY")
        assert idx == 1
        assert val == pytest.approx(0.2)


# ============================================================
# find_best_window — Negative Prices
# ============================================================

class TestFindBestWindowNegativePrices:
    """Negative prices occur in reality (Denmark/Germany wind surplus)."""

    def test_most_negative_is_cheapest(self):
        prices = [
            {"total": 0.5, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": -0.3, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": -0.5, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-01T03:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY")
        assert idx == 1  # -0.3 + -0.5 = -0.8
        assert val == pytest.approx(-0.8)

    def test_peak_with_negatives(self):
        prices = [
            {"total": -0.5, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": -0.1, "startsAt": "2024-01-01T01:00:00Z"},
            {"total": 0.8, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 1.2, "startsAt": "2024-01-01T03:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "peak", "HOURLY")
        assert idx == 2  # 0.8 + 1.2 = 2.0
        assert val == pytest.approx(2.0)


# ============================================================
# find_best_window — Time Restrictions
# ============================================================

class TestFindBestWindowTimeRestrictions:
    """Time restriction filtering."""

    def test_night_restriction(self):
        """Restrict to 20:00-06:00 should ignore daytime."""
        prices = [
            {"total": 0.1, "startsAt": "2024-01-01T10:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-01T11:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T22:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T23:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY", "20:00", "06:00")
        assert idx == 2
        assert val == pytest.approx(1.0)

    def test_daytime_restriction(self):
        """Restrict to 06:00-18:00 should ignore night."""
        prices = [
            {"total": 0.1, "startsAt": "2024-01-01T02:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-01T03:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T10:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T11:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY", "06:00", "18:00")
        assert idx == 2  # Daytime only
        assert val == pytest.approx(1.0)

    def test_impossible_restriction_returns_none(self):
        """If no window fits the restriction, return None."""
        prices = [
            {"total": 0.1, "startsAt": "2024-01-01T10:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-01T11:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY", "22:00", "06:00")
        assert idx is None

    def test_no_restriction_uses_all(self):
        """Empty restrictions should use all data."""
        prices = [
            {"total": 0.1, "startsAt": "2024-01-01T10:00:00Z"},
            {"total": 0.2, "startsAt": "2024-01-01T11:00:00Z"},
        ]
        idx, val = find_best_window(prices, 1, "best", "HOURLY", "", "")
        assert idx == 0


# ============================================================
# find_best_window — Cross-Midnight & 48h
# ============================================================

class TestFindBestWindowCrossMidnight:
    """Tests spanning midnight and combining today+tomorrow."""

    def test_cheapest_spans_midnight(self):
        prices = [
            {"total": 1.0, "startsAt": "2024-01-01T23:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-02T00:00:00Z"},
            {"total": 0.1, "startsAt": "2024-01-02T01:00:00Z"},
            {"total": 1.0, "startsAt": "2024-01-02T02:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY")
        assert idx == 1
        assert val == pytest.approx(0.2)

    def test_48h_cheapest_in_tomorrow(self):
        """Simulate 24h today + 24h tomorrow. Cheapest window is in tomorrow."""
        today = [{"total": 1.0, "startsAt": f"2024-01-01T{h:02d}:00:00Z"} for h in range(24)]
        tomorrow = [{"total": 0.8, "startsAt": f"2024-01-02T{h:02d}:00:00Z"} for h in range(24)]
        # Make hours 02:00-04:00 tomorrow super cheap
        tomorrow[2]["total"] = 0.01
        tomorrow[3]["total"] = 0.01
        tomorrow[4]["total"] = 0.01

        all_prices = today + tomorrow
        idx, val = find_best_window(all_prices, 3, "best", "HOURLY")
        assert idx == 26  # 24 (today) + 2 (02:00 tomorrow)
        assert val == pytest.approx(0.03)

    def test_48h_peak_in_today(self):
        """Simulate 48h. Peak window should be found in today."""
        today = [{"total": 0.5, "startsAt": f"2024-01-01T{h:02d}:00:00Z"} for h in range(24)]
        tomorrow = [{"total": 0.3, "startsAt": f"2024-01-02T{h:02d}:00:00Z"} for h in range(24)]
        # Make hours 17:00-19:00 today very expensive
        today[17]["total"] = 5.0
        today[18]["total"] = 5.0
        today[19]["total"] = 5.0

        all_prices = today + tomorrow
        idx, val = find_best_window(all_prices, 3, "peak", "HOURLY")
        assert idx == 17
        assert val == pytest.approx(15.0)


# ============================================================
# find_best_window — Realistic 24h Swedish Prices
# ============================================================

class TestFindBestWindowRealistic:
    """Realistic 24h Swedish electricity price curve."""

    @pytest.fixture
    def swedish_24h_prices(self):
        """Typical Swedish price curve: cheap night, expensive morning/evening."""
        hourly_totals = [
            0.25, 0.22, 0.20, 0.18, 0.19, 0.21,  # 00-05 Night (cheap)
            0.45, 0.85, 1.20, 1.10, 0.95, 0.80,  # 06-11 Morning peak
            0.70, 0.65, 0.60, 0.55, 0.65, 1.15,  # 12-17 Afternoon
            1.35, 1.25, 0.90, 0.60, 0.40, 0.30,  # 18-23 Evening peak then drop
        ]
        return [
            {"total": t, "startsAt": f"2024-01-15T{h:02d}:00:00+01:00"}
            for h, t in enumerate(hourly_totals)
        ]

    def test_cheapest_3h_is_night(self, swedish_24h_prices):
        """Cheapest 3 consecutive hours should be around 02:00-04:00."""
        idx, val = find_best_window(swedish_24h_prices, 3, "best", "HOURLY")
        assert idx == 2  # 02:00 (0.20 + 0.18 + 0.19 = 0.57)
        assert val == pytest.approx(0.57)

    def test_most_expensive_3h_is_morning(self, swedish_24h_prices):
        """Most expensive 3 consecutive hours should be around 07:00-09:00 or 17:00-19:00."""
        idx, val = find_best_window(swedish_24h_prices, 3, "peak", "HOURLY")
        # 17:00-19:00 = 1.15 + 1.35 + 1.25 = 3.75 vs 07:00-09:00 = 0.85 + 1.20 + 1.10 = 3.15
        assert idx == 17
        assert val == pytest.approx(3.75)

    def test_cheapest_1h(self, swedish_24h_prices):
        """Single cheapest hour should be 03:00 (0.18)."""
        idx, val = find_best_window(swedish_24h_prices, 1, "best", "HOURLY")
        assert idx == 3
        assert val == pytest.approx(0.18)


# ============================================================
# find_best_window — Edge Cases
# ============================================================

class TestFindBestWindowEdgeCases:
    """Robustness against invalid and extreme input."""

    def test_empty_list(self):
        assert find_best_window([], 1, "best", "HOURLY") == (None, None)

    def test_list_shorter_than_slots(self):
        prices = [{"total": 1.0, "startsAt": "2024-01-01T00:00:00Z"}]
        assert find_best_window(prices, 2, "best", "HOURLY") == (None, None)

    def test_exactly_enough_slots(self):
        """List length == slots_needed should return index 0."""
        prices = [
            {"total": 0.5, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T01:00:00Z"},
        ]
        idx, val = find_best_window(prices, 2, "best", "HOURLY")
        assert idx == 0
        assert val == pytest.approx(1.0)

    def test_malformed_data_missing_total(self):
        """Missing 'total' key should default to 0 via .get()."""
        prices = [
            {"not_total": 1.0, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.5, "startsAt": "2024-01-01T01:00:00Z"},
        ]
        idx, val = find_best_window(prices, 1, "best", "HOURLY")
        assert idx == 0  # 0 < 0.5


# ============================================================
# get_unit_label — Currency Unit Labels
# ============================================================

class TestGetUnitLabel:
    """Tests for currency-to-unit mapping."""

    def test_sek_default(self):
        assert get_unit_label("SEK", False) == "SEK/kWh"

    def test_sek_subunits(self):
        assert get_unit_label("SEK", True) == "öre/kWh"

    def test_nok_default(self):
        assert get_unit_label("NOK", False) == "NOK/kWh"

    def test_nok_subunits(self):
        """Norwegian krone uses same subunit name as Swedish."""
        assert get_unit_label("NOK", True) == "öre/kWh"

    def test_dkk_default(self):
        assert get_unit_label("DKK", False) == "DKK/kWh"

    def test_dkk_subunits(self):
        """Danish krone also uses öre."""
        assert get_unit_label("DKK", True) == "öre/kWh"

    def test_eur_default(self):
        assert get_unit_label("EUR", False) == "EUR/kWh"

    def test_eur_subunits(self):
        """Euro subunit is cent (ct)."""
        assert get_unit_label("EUR", True) == "ct/kWh"

    def test_unknown_currency_default(self):
        assert get_unit_label("USD", False) == "USD/kWh"

    def test_unknown_currency_subunits(self):
        """Unknown currencies get a generic 'Sub' label."""
        assert get_unit_label("USD", True) == "Sub/kWh"
        assert get_unit_label("GBP", True) == "Sub/kWh"


# ============================================================
# validate_time_format (from utils.py)
# ============================================================


class TestValidateTimeFormat:
    """Tests for HH:MM time validation used in config flow."""

    def test_valid_times(self):
        assert validate_time_format("00:00") is True
        assert validate_time_format("12:30") is True
        assert validate_time_format("23:59") is True
        assert validate_time_format("06:00") is True

    def test_invalid_hour(self):
        assert validate_time_format("25:00") is False
        assert validate_time_format("24:00") is False

    def test_invalid_minute(self):
        assert validate_time_format("12:60") is False
        assert validate_time_format("12:99") is False

    def test_invalid_format(self):
        assert validate_time_format("abc") is False
        assert validate_time_format("") is False
        assert validate_time_format("1:00") is False  # Missing leading zero
        assert validate_time_format("12:0") is False   # Missing trailing zero
        assert validate_time_format("12:00:00") is False  # HH:MM:SS not allowed

    def test_boundary_values(self):
        assert validate_time_format("00:00") is True
        assert validate_time_format("23:59") is True
        assert validate_time_format("19:59") is True
