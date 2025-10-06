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
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
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
    
    # Skapa EN sensor per hem
    if coordinator.data:
        for home_id, home_data in coordinator.data.items():
            entities.append(
                TibberPriceSensor(coordinator, home_id, home_name)
            )

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

        # Beräkna uppdateringsintervall för sensorn baserat på resolution
        if self.resolution == "QUARTER_HOURLY":
            self.sensor_update_interval = timedelta(minutes=15)
        else:  # HOURLY
            self.sensor_update_interval = timedelta(hours=1)

        # Vi uppdaterar inte automatiskt med interval, utan via time trigger
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Ingen automatisk uppdatering av data-hämtning
        )
        
        # Sätt upp time-baserade triggers för data-hämtning
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
            _LOGGER.info(f"Scheduled data fetch at {update_time.hour:02d}:{update_time.minute:02d}")

    async def _handle_time_trigger(self, now):
        """Handle time-based update trigger."""
        _LOGGER.info(f"Time trigger fired at {now}, fetching Tibber data")
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


class TibberPriceSensor(CoordinatorEntity, SensorEntity):
    """Unified sensor for Tibber electricity prices."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._attr_name = f"{home_name} Electricity Price"
        self._attr_unique_id = f"{home_id}_electricity_price"
        self._attr_native_unit_of_measurement = "kr/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:flash"
        
        # Sätt upp automatisk uppdatering av sensor-state (inte data-hämtning)
        self._setup_state_updates()

    def _setup_state_updates(self):
        """Setup automatic state updates based on resolution."""
        # Uppdatera sensor-state automatiskt varje kvart/timme
        async_track_time_interval(
            self.hass,
            self._update_state,
            self.coordinator.sensor_update_interval
        )

    async def _update_state(self, now=None):
        """Force sensor state update."""
        self.async_write_ha_state()

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

    @property
    def icon(self):
        """Return icon based on current price level."""
        level = self._get_current_level()
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
        return "mdi:flash"

    def _get_current_level(self):
        """Get current price level."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return "UNKNOWN"
        
        now = dt_util.now()
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        for price_point in today_prices:
            start_time = dt_util.parse_datetime(price_point["startsAt"])
            interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
            end_time = start_time + timedelta(minutes=interval)
            
            if start_time <= now < end_time:
                return price_point.get("level", "UNKNOWN")
        
        return "UNKNOWN"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data or self._home_id not in self.coordinator.data:
            return {}
        
        today_prices = self.coordinator.data[self._home_id]["today"]
        tomorrow_prices = self.coordinator.data[self._home_id]["tomorrow"]
        
        # Beräkna statistik för idag
        today_price_values = [p["total"] for p in today_prices]
        tomorrow_price_values = [p["total"] for p in tomorrow_prices]
        
        # Hitta nuvarande pris och nivå
        current_price = self.native_value
        current_level = self._get_current_level()
        
        attrs = {
            "current_price": current_price,
            "current_level": current_level,
            "resolution": self.coordinator.resolution,
            "today": {
                "prices": today_prices,
                "count": len(today_prices),
            },
            "tomorrow": {
                "prices": tomorrow_prices,
                "count": len(tomorrow_prices),
            },
        }
        
        # Statistik för idag
        if today_price_values:
            attrs["today"].update({
                "min": min(today_price_values),
                "max": max(today_price_values),
                "avg": round(sum(today_price_values) / len(today_price_values), 4),
            })
        
        # Statistik för imorgon
        if tomorrow_price_values:
            attrs["tomorrow"].update({
                "min": min(tomorrow_price_values),
                "max": max(tomorrow_price_values),
                "avg": round(sum(tomorrow_price_values) / len(tomorrow_price_values), 4),
            })
        
        return attrs