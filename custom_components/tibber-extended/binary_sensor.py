"""Binary Sensor platform for Tibber Extended."""
import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_HOME_NAME,
    CONF_BEST_PRICE_TARGET_HOURS,
    CONF_BEST_PRICE_SPANS,
    CONF_PEAK_PRICE_TARGET_HOURS,
    DEFAULT_BEST_PRICE_TARGET_HOURS,
    DEFAULT_PEAK_PRICE_TARGET_HOURS,
    DEFAULT_BEST_PRICE_SPANS,
    CONF_RESOLUTION,
    CONF_RESTRICT_TIME_START,
    CONF_RESTRICT_TIME_END,
    CONF_PRICE_THRESHOLD,
    DEFAULT_PRICE_THRESHOLD,
)
from .utils import find_best_window

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Extended binary sensors."""
    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    except KeyError:
        _LOGGER.error("Coordinator inte hittad, kan inte ladda binära sensorer")
        return

    home_name = entry.data.get(CONF_HOME_NAME, "Mitt Hem")
    resolution = entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY")

    # Om inga values finns i options, fall back till data, annars default
    best_spans_str = entry.options.get(CONF_BEST_PRICE_SPANS, entry.data.get(CONF_BEST_PRICE_SPANS, DEFAULT_BEST_PRICE_SPANS))
    peak_target = float(entry.options.get(CONF_PEAK_PRICE_TARGET_HOURS, entry.data.get(CONF_PEAK_PRICE_TARGET_HOURS, DEFAULT_PEAK_PRICE_TARGET_HOURS)))

    # Tolka spans (t.ex. "1, 3, 6")
    try:
        best_spans = [float(s.strip()) for s in str(best_spans_str).split(",") if s.strip()]
    except ValueError:
        _LOGGER.error(f"Ogiltigt format för best_price_spans: {best_spans_str}, använder default")
        best_spans = [float(DEFAULT_BEST_PRICE_SPANS)]

    entities = []

    if not coordinator.data:
        await coordinator.async_config_entry_first_refresh()

    if coordinator.data:
        for home_id in coordinator.data:
            _LOGGER.info(f"Creating binary sensors for home: {home_id}")
            
            # Skapa en sensor för varje best-span
            for span in best_spans:
                entities.append(
                    TibberTargetHoursBinarySensor(
                        coordinator, home_id, home_name, "best", span, resolution
                    )
                )
            
            # En peak-sensor per hem (som förut)
            entities.append(
                TibberTargetHoursBinarySensor(
                    coordinator, home_id, home_name, "peak", peak_target, resolution
                )
            )
            
            # Tröskel-sensor
            entities.append(
                TibberThresholdBinarySensor(
                    coordinator, home_id, home_name
                )
            )

    if entities:
        async_add_entities(entities, True)
        _LOGGER.info(f"Successfully setup Tibber binary sensors for {home_name}")


class TibberTargetHoursBinarySensor(BinarySensorEntity):
    """Binary sensor for cheapest/most expensive consecutive hours."""

    def __init__(self, coordinator, home_id, home_name, sensor_type, target_hours, resolution):
        """Initialize the binary sensor."""
        self.coordinator = coordinator
        self.home_id = home_id
        self.sensor_type = sensor_type  # "best" or "peak"
        self.target_hours = float(target_hours)
        self.resolution = resolution

        # Läs av optional time restrictions
        self.restrict_start = coordinator.entry.options.get(
            CONF_RESTRICT_TIME_START, coordinator.entry.data.get(CONF_RESTRICT_TIME_START, "")
        )
        self.restrict_end = coordinator.entry.options.get(
            CONF_RESTRICT_TIME_END, coordinator.entry.data.get(CONF_RESTRICT_TIME_END, "")
        )

        if sensor_type == "best":
            type_name = f"Best Price {target_hours}h"
            self._attr_unique_id = f"tibber_extended_{home_id}_{sensor_type}_{target_hours}h_price"
        else:
            type_name = "Peak Price"
            self._attr_unique_id = f"tibber_extended_{home_id}_{sensor_type}_price"
            
        self._attr_name = f"{home_name} {type_name}"
        self._attr_icon = "mdi:cash-check" if sensor_type == "best" else "mdi:cash-remove"

        self.period_start = None
        self.period_end = None
        self.avg_price = None

    @property
    def should_poll(self):
        """Return False as updates are handled by the coordinator."""
        return False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if not self.period_start or not self.period_end:
            return False

        now = dt_util.now()
        try:
            from dateutil.parser import isoparse
            start_time = isoparse(self.period_start)
            end_time = isoparse(self.period_end)
            return start_time <= now < end_time
        except Exception as e:
            _LOGGER.error(f"Fel vid tolkning av datum i binär sensor: {e}")
            return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            "target_hours": self.target_hours,
        }
        if self.period_start:
            attrs["period_start"] = self.period_start
        if self.period_end:
            attrs["period_end"] = self.period_end
        if self.avg_price is not None:
            attrs["avg_price_in_period"] = round(self.avg_price, 4)

        return attrs

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._calculate_period()
        self.async_write_ha_state()

    def _calculate_period(self):
        """Find the cheapest/most expensive consecutive window for today."""
        data = self.coordinator.data
        if not data or self.home_id not in data:
            return

        today_prices = data[self.home_id].get("today", [])
        tomorrow_prices = data[self.home_id].get("tomorrow", [])

        # Kombinera listorna för att kunna hitta fönster som spänner över midnatt
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return

        slots_needed = int(self.target_hours * (4 if self.resolution == "QUARTER_HOURLY" else 1))

        best_window_start, best_window_sum = find_best_window(
            all_prices,
            slots_needed,
            self.sensor_type,
            self.resolution,
            self.restrict_start,
            self.restrict_end
        )

        if best_window_start is None:
            self.period_start = None
            self.period_end = None
            self.avg_price = None
            return

        best_window = all_prices[best_window_start:best_window_start + slots_needed]

        self.period_start = best_window[0]["startsAt"]

        from dateutil.parser import isoparse
        end_dt = isoparse(best_window[-1]["startsAt"])
        if self.resolution == "QUARTER_HOURLY":
            end_dt += timedelta(minutes=15)
        else:
            end_dt += timedelta(hours=1)

        self.period_end = end_dt.isoformat()
        self.avg_price = best_window_sum / slots_needed


class TibberThresholdBinarySensor(BinarySensorEntity):
    """Binary sensor that is ON when price is below a threshold."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the binary sensor."""
        self.coordinator = coordinator
        self.home_id = home_id
        self._attr_name = f"{home_name} Below Price Threshold"
        self._attr_unique_id = f"tibber_extended_{home_id}_price_threshold"
        self._attr_icon = "mdi:cash-multiple"

    @property
    def should_poll(self):
        """Return False as updates are handled by the coordinator."""
        return False

    @property
    def is_on(self):
        """Return true if the current price is below the threshold."""
        if not self.coordinator.data or self.home_id not in self.coordinator.data:
            return False

        # Hämta nuvarande tröskel från konfig
        threshold = float(self.coordinator.entry.options.get(
            CONF_PRICE_THRESHOLD,
            self.coordinator.entry.data.get(CONF_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
        ))

        today_prices = self.coordinator.data[self.home_id].get("today", [])
        if not today_prices:
            return False

        # Matchning mot hemmets tidszon
        now = dt_util.now()
        for p in today_prices:
            st = dt_util.parse_datetime(p["startsAt"])
            if not st:
                continue

            home_tz_name = self.coordinator._home_timezones.get(self.home_id)
            if home_tz_name:
                try:
                    from zoneinfo import ZoneInfo
                    st = st.astimezone(ZoneInfo(home_tz_name))
                    now_tz = now.astimezone(ZoneInfo(home_tz_name))
                except Exception:
                    now_tz = now
            else:
                now_tz = now

            interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
            if st <= now_tz < st + timedelta(minutes=interval):
                return float(p.get("total", 0)) < threshold

        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        threshold = float(self.coordinator.entry.options.get(
            CONF_PRICE_THRESHOLD,
            self.coordinator.entry.data.get(CONF_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
        ))
        return {
            "threshold": threshold,
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        # Vi triggar även en uppdatering varje kvart/timme för att hålla kollen
        minutes = [0, 15, 30, 45] if self.coordinator.resolution == "QUARTER_HOURLY" else [0]
        for minute in minutes:
            from homeassistant.helpers.event import async_track_time_change
            self.async_on_remove(
                async_track_time_change(self.hass, self._update_state, minute=minute, second=2)
            )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def _update_state(self, now=None):
        """Update the state without a coordinator fetch."""
        self.async_write_ha_state()

