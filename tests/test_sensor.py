import pytest

def mock_format_price_value(value, subunits):
    if value is None:
        return None
    return round(value * 100, 2) if subunits else round(value, 4)

def build_timeline_data(today_prices, tomorrow_prices, use_subunits):
    """
    Kopia av logiken i sensor.py för att generera timeline_data.
    Måste returnera en lista av dicts med start_time och price_per_kwh.
    """
    timeline_data = []
    for p in today_prices + tomorrow_prices:
        timeline_data.append({
            "start_time": p.get("startsAt"),
            "price_per_kwh": mock_format_price_value(p.get("total", 0), use_subunits)
        })
    return timeline_data

class TestTimelineData:
    def test_timeline_data_format(self):
        today = [
            {"total": 0.5, "startsAt": "2024-01-01T00:00:00Z"},
            {"total": 0.6, "startsAt": "2024-01-01T01:00:00Z"},
        ]
        tomorrow = [
            {"total": 0.7, "startsAt": "2024-01-02T00:00:00Z"}
        ]
        
        result = build_timeline_data(today, tomorrow, False)
        
        # Verify length
        assert len(result) == 3
        
        # Verify specific keys required by ha-price-timeline-card
        assert "start_time" in result[0]
        assert "price_per_kwh" in result[0]
        
        # Verify values
        assert result[0]["price_per_kwh"] == 0.5
        assert result[1]["price_per_kwh"] == 0.6
        assert result[2]["price_per_kwh"] == 0.7
        assert result[2]["start_time"] == "2024-01-02T00:00:00Z"

    def test_timeline_data_subunits(self):
        today = [
            {"total": 0.555, "startsAt": "2024-01-01T00:00:00Z"},
        ]
        
        result = build_timeline_data(today, [], True)
        
        assert result[0]["price_per_kwh"] == 55.5
