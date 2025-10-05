import logging
from datetime import datetime, timedelta
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
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_RESOLUTION,
    CONF_UPDATE_HOUR,
    CONF_UPDATE_MINUTE,
    DEFAULT_UPDATE_HOUR,
    DEFAULT_UPDATE_MINUTE,
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
    
    # Skapa sensorer för varje hem
    if coordinator.data:
        for home_id, home_data in coordinator.data.items():
            entities.extend([
                TibberCurrentPriceSensor(coordinator, home_id, home_data["name"]),
                TibberCurrentLevelSensor(coordinator, home_id, home_data["name"]),
                TibberTodayPricesSensor(coordinator, home_id, home_data["name"]),
                TibberTomorrowPricesSensor(coordinator, home_id, home_data["name"]),
            ])

    async_add_entities(entities)


class TibberDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tibber data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.token = entry.data[CONF_ACCESS_TOKEN]
        self.resolution = entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY")
        self.update_hour = entry.data.get(CONF_UPDATE_HOUR, DEFAULT_UPDATE_HOUR)
        self.update_minute = entry.data.get(CONF_UPDATE_MINUTE, DEFAULT_UPDATE_MINUTE)

        # Beräkna nästa uppdateringstid
        update_interval = self._calculate_next_update()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def _calculate_next_update(self) -> timedelta:
        """Calculate time until next update."""
        now = dt_util.now()
        target_time = now.replace(
            hour=self.update_hour, 
            minute=self.update_minute, 
            second=0, 
            microsecond=0
        )
        
        if now >= target_time:
            target_time += timedelta(days=1)
        
        return target_time - now

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
        self._attr_name = f"Tibber {home_name} Current Price"
        self._attr_unique_id = f"{home_id}_current_price"
        self._attr_native_unit_of_measurement = "kr/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:currency-usd"

    @property
    def native_value(self):
        """Return the current price."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return None
        
        now = dt_util.now()
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        for price_point in today_prices:
            start_time = dt_util.parse_datetime(price_point["startsAt"])
            # För QUARTER_HOURLY är intervallet 15 min, för HOURLY är det 60 min
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
        self._attr_name = f"Tibber {home_name} Current Level"
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
                return price_point.get("level", "UNKNOWN")
        
        return "UNKNOWN"


class TibberTodayPricesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for today's prices."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"Tibber {home_name} Today Prices"
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
        
        return {
            "prices": self.coordinator.data[self._home_id]["today"],
            "resolution": self.coordinator.resolution,
        }


class TibberTomorrowPricesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for tomorrow's prices."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"Tibber {home_name} Tomorrow Prices"
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
        
        return {
            "prices": self.coordinator.data[self._home_id]["tomorrow"],
            "resolution": self.coordinator.resolution,
        }