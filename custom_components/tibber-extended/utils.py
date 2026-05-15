"""Utility functions for Tibber Extended."""
import logging
import re
from datetime import datetime
from dateutil.parser import isoparse

_LOGGER = logging.getLogger(__name__)


def validate_time_format(time_str: str) -> bool:
    """Validate time format HH:MM."""
    pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    return bool(re.match(pattern, time_str))

def parse_spans(spans_str):
    """
    Parse a span string with optional time restrictions.
    Format: "1, 3[22:00-06:00], 6[10:00-20:00]"
    Returns a list of tuples: (span, restrict_start, restrict_end)
    """
    results = []
    if not spans_str:
        return results

    items = [s.strip() for s in str(spans_str).split(",") if s.strip()]

    for item in items:
        # Match "3[22:00-06:00]" or just "3" or "1.5"
        match = re.match(r"^([\d.]+)(?:\[([\d:]+)-([\d:]+)\])?$", item)
        if match:
            try:
                span = float(match.group(1))
                start = match.group(2)
                end = match.group(3)

                if start and end:
                    if not validate_time_format(start) or not validate_time_format(end):
                        _LOGGER.warning(f"Invalid time format in span: {item}")
                        start, end = None, None

                results.append((span, start, end))
            except ValueError:
                _LOGGER.warning(f"Invalid span value in item: {item}")
        else:
            _LOGGER.warning(f"Failed to parse span item: {item}")

    return results


def find_best_window(all_prices, slots_needed, sensor_type, resolution, restrict_start=None, restrict_end=None):
    """
    Find the best (cheapest or most expensive) consecutive window of prices.
    Returns (start_index, window_sum) or (None, None).
    """
    if not all_prices or len(all_prices) < slots_needed:
        return None, None

    best_window_start = None
    best_window_sum = float("inf") if sensor_type == "best" else float("-inf")

    start_t, end_t = None, None
    if restrict_start and restrict_end:
        try:
            start_t = datetime.strptime(restrict_start, "%H:%M").time()
            end_t = datetime.strptime(restrict_end, "%H:%M").time()
        except ValueError:
            _LOGGER.error("Invalid time format for restriction")
            return None, None

    for i in range(len(all_prices) - slots_needed + 1):
        window = all_prices[i:i + slots_needed]

        # Check time restrictions
        valid_window = True
        if start_t and end_t:
            for p in window:
                try:
                    p_time = isoparse(p["startsAt"]).time()
                    if start_t <= end_t:
                        if not (start_t <= p_time < end_t):
                            valid_window = False
                            break
                    else: # Crosses midnight
                        if not (p_time >= start_t or p_time < end_t):
                            valid_window = False
                            break
                except Exception:
                    valid_window = False
                    break

        if not valid_window:
            continue

        window_sum = sum(p.get("total", 0) for p in window)

        if sensor_type == "best":
            if window_sum < best_window_sum:
                best_window_sum = window_sum
                best_window_start = i
        else: # "peak"
            if window_sum > best_window_sum:
                best_window_sum = window_sum
                best_window_start = i

    return best_window_start, best_window_sum

def format_price_value(value, use_subunits):
    """Format a price value based on subunit setting."""
    if value is None:
        return None
    return round(value * 100, 2) if use_subunits else round(value, 4)


def get_unit_label(currency, use_subunits):
    """Return the correct unit label for a given currency and subunit setting.

    Examples:
        get_unit_label("SEK", False) -> "SEK/kWh"
        get_unit_label("SEK", True)  -> "öre/kWh"
        get_unit_label("EUR", True)  -> "ct/kWh"
    """
    if use_subunits:
        if currency in ("SEK", "NOK", "DKK"):
            return "öre/kWh"
        elif currency == "EUR":
            return "ct/kWh"
        else:
            return "Sub/kWh"
    return f"{currency}/kWh"
