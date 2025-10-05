"""Sensor platform for Tibber Extended."""
import logging
from datetime import datetime, timedelta, time
import aiohttp
import asyncio

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_RESOLUTION,
    CONF_UPDATE_TIMES,
    CONF_HOME_NAME,
    DEFAULT_UPDATE_TIMES,
    TIBBER_API_URL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Extended sensors."""
    coordinator = TibberDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    home_name = entry.data.get(CONF_HOME_NAME, "Mitt Hem")
    
    # Skapa sensorer för varje hem från API
    if coordinator.data:
        for home_id, home_data in coordinator.data.items():
            # Använd custom home_name från config istället för API nickname
            entities.extend([
                TibberCurrentPriceSensor(coordinator, home_id, home_name),
                TibberCurrentLevelSensor(coordinator, home_id, home_name),
                TibberTodayPricesSensor(coordinator, home_id, home_name),
                TibberTomorrowPricesSensor(coordinator, home_id, home_name),
            ])

    async_add_entities(entities)


class TibberDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tibber data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.token = entry.data[CONF_ACCESS_TOKEN]
        self.resolution = entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY")
        self.update_times = entry.data.get(CONF_UPDATE_TIMES, DEFAULT_UPDATE_TIMES)
        
        # Konvertera update_times till time-objekt
        self.update_times_parsed = []
        for time_str in self.update_times:
            try:
                hour, minute = map(int, time_str.split(":"))
                self.update_times_parsed.append(time(hour=hour, minute=minute))
            except ValueError:
                _LOGGER.error(f"Invalid time format: {time_str}")

        # Vi uppdaterar inte automatiskt med interval, utan via time trigger
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Ingen automatisk uppdatering
        )
        
        # Sätt upp time-baserade triggers
        self._setup_time_triggers()

    def _setup_time_triggers(self):
        """Setup time-based update triggers."""
        for update_time in self.update_times_parsed:
            async_track_time_change(
                self.hass,
                self._handle_time_trigger,
                hour=update_time.hour,
                minute=update_time.minute,
                second=0,
            )
            _LOGGER.info(f"Scheduled update at {update_time.hour:02d}:{update_time.minute:02d}")

    async def _handle_time_trigger(self, now):
        """Handle time-based update trigger."""
        _LOGGER.info(f"Time trigger fired at {now}, updating Tibber data")
        await self.async_request_refresh()

    async def _async_update_data(self):
        """Fetch data from Tibber API."""
        query = """
        {
            viewer {
                homes {
                    id
                    appNickname
                    currentSubscription {
                        priceInfo(resolution: %s) {
                            today {
                                total
                                startsAt
                                level
                            }
                            tomorrow {
                                total
                                startsAt
                                level
                            }
                        }
                    }
                }
            }
        }
        """ % self.resolution

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TIBBER_API_URL,
                    json={"query": query},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"API error: {response.status}")
                    
                    data = await response.json()
                    
                    if "errors" in data:
                        raise UpdateFailed(f"GraphQL errors: {data['errors']}")
                    
                    # Parse the data
                    homes_data = {}
                    for home in data["data"]["viewer"]["homes"]:
                        home_id = home["id"]
                        price_info = home.get("currentSubscription", {}).get("priceInfo", {})
                        
                        homes_data[home_id] = {
                            "name": home.get("appNickname", "Home"),
                            "today": price_info.get("today", []),
                            "tomorrow": price_info.get("tomorrow", []),
                        }
                    
                    _LOGGER.info(f"Successfully fetched data for {len(homes_data)} homes")
                    return homes_data

        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching data: {err}")
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching data: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")


class TibberCurrentPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current electricity price."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"{home_name} Current Price"
        self._attr_unique_id = f"{home_id}_current_price"
        self._attr_native_unit_of_measurement = "kr/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self):
        """Return the current price."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return None
        
        now = dt_util.now()
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        for price_point in today_prices:
            start_time = dt_util.parse_datetime(price_point["startsAt"])
            interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
            end_time = start_time + timedelta(minutes=interval)
            
            if start_time <= now < end_time:
                return round(price_point["total"], 4)
        
        return None


class TibberCurrentLevelSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current price level."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"{home_name} Current Level"
        self._attr_unique_id = f"{home_id}_current_level"
        self._attr_icon = "mdi:chart-bell-curve"

    @property
    def native_value(self):
        """Return the current price level."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return None
        
        now = dt_util.now()
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        for price_point in today_prices:
            start_time = dt_util.parse_datetime(price_point["startsAt"])
            interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
            end_time = start_time + timedelta(minutes=interval)
            
            if start_time <= now < end_time:
                level = price_point.get("level", "UNKNOWN")
                return level
        
        return "UNKNOWN"
    
    @property
    def icon(self):
        """Return icon based on price level."""
        level = self.native_value
        if level == "VERY_CHEAP":
            return "mdi:arrow-down-bold"
        elif level == "CHEAP":
            return "mdi:arrow-down"
        elif level == "NORMAL":
            return "mdi:minus"
        elif level == "EXPENSIVE":
            return "mdi:arrow-up"
        elif level == "VERY_EXPENSIVE":
            return "mdi:arrow-up-bold"
        return "mdi:help-circle"


class TibberTodayPricesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for today's prices."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"{home_name} Today Prices"
        self._attr_unique_id = f"{home_id}_today_prices"
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self):
        """Return number of price points."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return 0
        
        return len(self.coordinator.data[self._home_id]["today"])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return {}
        
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        # Beräkna extra statistik
        prices_only = [p["total"] for p in today_prices]
        
        attrs = {
            "prices": today_prices,
            "resolution": self.coordinator.resolution,
        }
        
        if prices_only:
            attrs.update({
                "min_price": min(prices_only),
                "max_price": max(prices_only),
                "avg_price": round(sum(prices_only) / len(prices_only), 4),
            })
        
        return attrs


class TibberTomorrowPricesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for tomorrow's prices."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"{home_name} Tomorrow Prices"
        self._attr_unique_id = f"{home_id}_tomorrow_prices"
        self._attr_icon = "mdi:chart-line-variant"

    @property
    def native_value(self):
        """Return number of price points."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return 0
        
        return len(self.coordinator.data[self._home_id]["tomorrow"])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return {}
        
        tomorrow_prices = self.coordinator.data[self._home_id]["tomorrow"]
        
        # Beräkna extra statistik
        prices_only = [p["total"] for p in tomorrow_prices]
        
        attrs = {
            "prices": tomorrow_prices,
            "resolution": self.coordinator.resolution,
        }
        
        if prices_only:
            attrs.update({
                "min_price": min(prices_only),
                "max_price": max(prices_only),
                "avg_price": round(sum(prices_only) / len(prices_only), 4),
            })
        
        return attrs