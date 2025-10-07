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
    CONF_CURRENCY,
    DEFAULT_UPDATE_TIMES,
    DEFAULT_CURRENCY,
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
    
    # Försök hämta data första gången
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data: %s", err)
    
    home_name = entry.data.get(CONF_HOME_NAME, "Mitt Hem")
    currency = entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
    entities = []
    
    # Skapa sensor även om ingen data finns än
    if coordinator.data:
        for home_id, home_data in coordinator.data.items():
            _LOGGER.info(f"Creating sensor for home: {home_id}")
            entities.append(TibberPriceSensor(coordinator, home_id, home_name, currency))
    else:
        _LOGGER.warning("No data available yet, creating sensor anyway")
        entities.append(TibberPriceSensor(coordinator, "pending", home_name, currency))

    async_add_entities(entities, True)
    _LOGGER.info(f"Added {len(entities)} Tibber sensors")


class TibberDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tibber data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.token = entry.data[CONF_ACCESS_TOKEN]
        self.resolution = entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY")
        self.update_times = entry.data.get(CONF_UPDATE_TIMES, DEFAULT_UPDATE_TIMES)
        self.entry = entry
        
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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        
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
        _LOGGER.debug(f"Fetching data with resolution: {self.resolution}")
        
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
                                energy
                                tax
                                startsAt
                                level
                            }
                            tomorrow {
                                total
                                energy
                                tax
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
                        error_msg = data['errors'][0].get('message', 'Unknown error')
                        _LOGGER.error(f"GraphQL error: {error_msg}")
                        raise UpdateFailed(f"GraphQL error: {error_msg}")
                    
                    homes_data = {}
                    viewer_data = data.get("data", {}).get("viewer", {})
                    homes = viewer_data.get("homes", [])
                    
                    if not homes:
                        _LOGGER.warning("No homes found in Tibber account")
                        return homes_data
                    
                    for home in homes:
                        home_id = home["id"]
                        subscription = home.get("currentSubscription")
                        
                        if not subscription:
                            _LOGGER.warning(f"No subscription found for home {home_id}")
                            continue
                        
                        price_info = subscription.get("priceInfo", {})
                        
                        homes_data[home_id] = {
                            "name": home.get("appNickname", "Home"),
                            "today": price_info.get("today", []),
                            "tomorrow": price_info.get("tomorrow", []),
                        }
                        
                        _LOGGER.debug(
                            f"Home {home_id}: {len(homes_data[home_id]['today'])} today prices, "
                            f"{len(homes_data[home_id]['tomorrow'])} tomorrow prices"
                        )
                    
                    _LOGGER.info(f"Successfully fetched data for {len(homes_data)} home(s)")
                    return homes_data

        except asyncio.TimeoutError as err:
            _LOGGER.error(f"Timeout fetching data: {err}")
            raise UpdateFailed(f"Timeout fetching data: {err}")
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Network error: {err}")
            raise UpdateFailed(f"Error fetching data: {err}")
        except KeyError as err:
            _LOGGER.error(f"Unexpected API response structure: {err}")
            raise UpdateFailed(f"Invalid API response: {err}")
        except Exception as err:
            _LOGGER.error(f"Unexpected error: {err}")
            raise UpdateFailed(f"Unexpected error: {err}")


class TibberPriceSensor(CoordinatorEntity, SensorEntity):
    """Unified sensor for Tibber electricity prices."""

    def __init__(self, coordinator, home_id, home_name, currency):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._currency = currency
        self._attr_name = f"{home_name} Electricity Price"
        self._attr_unique_id = f"{home_id}_electricity_price"
        self._attr_native_unit_of_measurement = f"{currency}/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:flash"
        self._attr_available = False
        self._update_interval_remover = None
        
        _LOGGER.info(f"Initialized sensor: {self._attr_name} (ID: {self._attr_unique_id})")

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        self._update_interval_remover = async_track_time_interval(
            self.hass,
            self._update_state,
            self.coordinator.sensor_update_interval
        )
        _LOGGER.debug(
            f"State updates every {self.coordinator.sensor_update_interval} "
            f"for {self._attr_name}"
        )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        
        if self._update_interval_remover:
            self._update_interval_remover()
            self._update_interval_remover = None

    async def _update_state(self, now=None):
        """Force sensor state update."""
        self.async_write_ha_state()
        _LOGGER.debug(f"State updated for {self._attr_name}")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        
        if not self.coordinator.data:
            return False
        
        if self._home_id == "pending" and self.coordinator.data:
            first_home_id = list(self.coordinator.data.keys())[0]
            self._home_id = first_home_id
            self._attr_unique_id = f"{first_home_id}_electricity_price"
            _LOGGER.info(f"Updated home_id from pending to {first_home_id}")
        
        return self._home_id in self.coordinator.data

    def _get_current_price_point(self):
        """Get current price point data."""
        if not self.available:
            return None
        
        now = dt_util.now()
        today_prices = self.coordinator.data[self._home_id]["today"]
        
        if not today_prices:
            return None
        
        for price_point in today_prices:
            try:
                start_time = dt_util.parse_datetime(price_point["startsAt"])
                interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
                end_time = start_time + timedelta(minutes=interval)
                
                if start_time <= now < end_time:
                    return price_point
            except (KeyError, ValueError, TypeError) as err:
                _LOGGER.error(f"Error parsing price point: {err}")
                continue
        
        return None

    @property
    def native_value(self):
        """Return the current total price."""
        price_point = self._get_current_price_point()
        if price_point:
            return round(price_point.get("total", 0), 4)
        return None

    @property
    def icon(self):
        """Return icon based on current price level."""
        price_point = self._get_current_price_point()
        if price_point:
            level = price_point.get("level", "UNKNOWN")
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

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.available:
            return {
                "current_total": None,
                "current_energy": None,
                "current_tax": None,
                "current_level": "UNKNOWN",
                "current_starts_at": None,
                "currency": self._currency,
                "resolution": self.coordinator.resolution,
                "today": {"prices": [], "count": 0},
                "tomorrow": {"prices": [], "count": 0},
            }
        
        today_prices = self.coordinator.data[self._home_id]["today"]
        tomorrow_prices = self.coordinator.data[self._home_id]["tomorrow"]
        
        current_price_point = self._get_current_price_point()
        
        def calculate_stats(prices, field):
            """Calculate min/max/avg for a specific field."""
            values = [p.get(field, 0) for p in prices if field in p]
            if values:
                return {
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "avg": round(sum(values) / len(values), 4),
                }
            return {}
        
        attrs = {
            "currency": self._currency,
            "resolution": self.coordinator.resolution,
            "today": {
                "prices": today_prices,
                "count": len(today_prices),
                "total": calculate_stats(today_prices, "total"),
                "energy": calculate_stats(today_prices, "energy"),
            },
            "tomorrow": {
                "prices": tomorrow_prices,
                "count": len(tomorrow_prices),
                "total": calculate_stats(tomorrow_prices, "total"),
                "energy": calculate_stats(tomorrow_prices, "energy"),
            },
        }
        
        if current_price_point:
            attrs.update({
                "current_total": round(current_price_point.get("total", 0), 4),
                "current_energy": round(current_price_point.get("energy", 0), 4),
                "current_tax": round(current_price_point.get("tax", 0), 4),
                "current_level": current_price_point.get("level", "UNKNOWN"),
                "current_starts_at": current_price_point.get("startsAt"),
            })
        else:
            attrs.update({
                "current_total": None,
                "current_energy": None,
                "current_tax": None,
                "current_level": "UNKNOWN",
                "current_starts_at": None,
            })
        
        return attrs
