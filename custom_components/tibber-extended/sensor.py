"""Sensor platform for Tibber Extended."""
import logging
from datetime import timedelta, time
import aiohttp
import asyncio
import time as time_mod

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
    CONF_CURRENCY,
    DEFAULT_UPDATE_TIMES,
    DEFAULT_CURRENCY,
    TIBBER_API_URL,
)
from .utils import format_price_value

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Extended sensors."""
    coordinator = TibberDataCoordinator(hass, entry)
    
    # Spara koordinator så button.py kan hitta den
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    
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
        self._last_midnight_shift = None  # Håll koll på när vi senast flyttade data
        
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
        # Ordinarie uppdateringstider
        for update_time in self.update_times_parsed:
            async_track_time_change(
                self.hass,
                self._handle_time_trigger,
                hour=update_time.hour,
                minute=update_time.minute,
                second=0,
            )
            _LOGGER.info(f"Scheduled data fetch at {update_time.hour:02d}:{update_time.minute:02d}")
        
        # Flytta tomorrow → today 5 sekunder före midnatt (UTAN API-anrop)
        async_track_time_change(
            self.hass,
            self._handle_midnight_shift,
            hour=23,
            minute=59,
            second=55,  # 5 sekunder före midnatt
        )
        _LOGGER.info("Scheduled price shift 5 seconds before midnight (23:59:55)")

    async def _handle_time_trigger(self, now):
        """Handle time-based update trigger."""
        _LOGGER.info(f"Time trigger fired at {now}, fetching Tibber data")
        await self.async_request_refresh()

    async def _handle_midnight_shift(self, now):
        """Shift tomorrow prices to today at midnight."""
        current_date = now.date()
        
        # Kontrollera så vi inte kör flera gånger samma natt
        if self._last_midnight_shift == current_date:
            _LOGGER.debug("Midnight shift already performed today")
            return
        
        _LOGGER.info(f"Midnight shift triggered at {now}")
        
        if not self.data:
            _LOGGER.warning("No data to shift at midnight")
            return
        
        # Flytta tomorrow → today för alla hem
        for home_id in self.data.keys():
            tomorrow_prices = self.data[home_id].get("tomorrow", [])
            
            if tomorrow_prices:
                _LOGGER.info(
                    f"Shifting {len(tomorrow_prices)} prices from tomorrow to today "
                    f"for home {home_id}"
                )
                
                # Flytta morgondagens priser till idag
                self.data[home_id]["today"] = tomorrow_prices
                # Töm morgondagens priser
                self.data[home_id]["tomorrow"] = []
            else:
                _LOGGER.warning(
                    f"No tomorrow prices available to shift for home {home_id}"
                )
        
        # Markera att vi gjort shiften
        self._last_midnight_shift = current_date
        
        # Trigga uppdatering av alla sensorer
        self.async_set_updated_data(self.data)
        _LOGGER.info("Midnight shift completed, sensors updated")

    async def _async_update_data(self):
        """Fetch data from Tibber API."""
        _LOGGER.debug(f"Fetching data with resolution: {self.resolution}")
        
        # Bara hämta morgondagens priser efter kl 12:45 för att undvika 504 Timeout på stora förfrågningar
        now_time = dt_util.now().time()
        fetch_tomorrow = now_time >= time(12, 45)
        
        tomorrow_query = """
                            tomorrow {
                                total
                                energy
                                tax
                                startsAt
                                level
                            }""" if fetch_tomorrow else ""

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
                            }%s
                        }
                    }
                }
            }
        }
        """ % (self.resolution, tomorrow_query)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        max_retries = 2
        request_start_time = time_mod.time()
        
        for attempt in range(max_retries):
            try:
                _LOGGER.debug(f"Starting API request (Attempt {attempt + 1}/{max_retries})")
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        TIBBER_API_URL,
                        json={"query": query},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=45),
                    ) as response:
                        if response.status != 200:
                            if response.status == 504 and attempt < max_retries - 1:
                                _LOGGER.warning(f"504 Gateway Timeout from Tibber API (Attempt {attempt + 1}/{max_retries}), retrying...")
                                await asyncio.sleep(2)
                                continue
                            raise UpdateFailed(f"API error: {response.status} (Attempt {attempt + 1})")
                        
                        elapsed = round(time_mod.time() - request_start_time, 2)
                        _LOGGER.debug(f"API response received in {elapsed}s")
                        
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
                            
                            # Hämta befintlig tomorrow data om vi har någon och inte hämtar ny
                            existing_tomorrow = []
                            if self.data and home_id in self.data:
                                existing_tomorrow = self.data[home_id].get("tomorrow", [])
                                
                            homes_data[home_id] = {
                                "name": home.get("appNickname", "Home"),
                                "today": price_info.get("today", []),
                                "tomorrow": price_info.get("tomorrow", existing_tomorrow),
                            }
                            
                            _LOGGER.debug(
                                f"Home {home_id}: {len(homes_data[home_id]['today'])} today prices, "
                                f"{len(homes_data[home_id]['tomorrow'])} tomorrow prices"
                            )
                        
                        _LOGGER.info(
                            f"Successfully fetched data for {len(homes_data)} home(s) "
                            f"in {elapsed}s (Tomorrow fetched: {fetch_tomorrow})"
                        )
                        return homes_data

            except asyncio.TimeoutError as err:
                if attempt < max_retries - 1:
                    _LOGGER.warning("Timeout from Tibber API, retrying...")
                    await asyncio.sleep(2)
                    continue
                _LOGGER.error(f"Timeout fetching data: {err}")
                raise UpdateFailed(f"Timeout fetching data: {err}")
            except aiohttp.ClientError as err:
                if attempt < max_retries - 1:
                    _LOGGER.warning("Network error, retrying...")
                    await asyncio.sleep(2)
                    continue
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
        
        # Läs av inställningen för underenheter (öre/ct) från options eller data
        self.use_subunits = coordinator.entry.options.get(
            "use_subunits", coordinator.entry.data.get("use_subunits", False)
        )
        
        from .utils import get_unit_label
        self._attr_native_unit_of_measurement = get_unit_label(currency, self.use_subunits)
    
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:flash"
        self._attr_available = False
        self._update_listeners = []
        
        _LOGGER.info(f"Initialized sensor: {self._attr_name} (ID: {self._attr_unique_id})")

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Schedule updates to align with the clock
        if self.coordinator.resolution == "QUARTER_HOURLY":
            minutes = [0, 15, 30, 45]
            _LOGGER.debug(
                f"Scheduling state updates at minutes {minutes} for {self._attr_name}"
            )
        else:  # HOURLY
            minutes = [0]
            _LOGGER.debug(
                f"Scheduling state updates at minute 0 for {self._attr_name}"
            )

        for minute in minutes:
            self._update_listeners.append(
                async_track_time_change(
                    self.hass, self._update_state, minute=minute, second=1
                )
            )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        
        for remover in self._update_listeners:
            remover()
        self._update_listeners = []

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
        
        # Ingen kombinering behövs - today har alltid rätt data tack vare midnight shift!
        if not today_prices:
            return None
        
        for price_point in today_prices:
            try:
                start_time = dt_util.parse_datetime(price_point["startsAt"])
                if not start_time:
                    continue
                    
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
            return format_price_value(price_point.get("total", 0), self.use_subunits)
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
                    "min": format_price_value(min(values), self.use_subunits),
                    "max": format_price_value(max(values), self.use_subunits),
                    "avg": format_price_value(sum(values) / len(values), self.use_subunits),
                }
            return {}

        # Bygg data för ha-price-timeline-card
        timeline_data = []
        for p in today_prices + tomorrow_prices:
            timeline_data.append({
                "start_time": p.get("startsAt"),
                "price_per_kwh": format_price_value(p.get("total", 0), self.use_subunits)
            })
            
        current_total = current_price_point.get("total") if current_price_point else None
        current_energy = current_price_point.get("energy") if current_price_point else None
        current_tax = current_price_point.get("tax") if current_price_point else None
        
        attrs = {
            "current_total": format_price_value(current_total, self.use_subunits),
            "current_energy": format_price_value(current_energy, self.use_subunits),
            "current_tax": format_price_value(current_tax, self.use_subunits),
            "current_level": current_price_point.get("level", "UNKNOWN") if current_price_point else "UNKNOWN",
            "current_starts_at": current_price_point.get("startsAt") if current_price_point else None,
            "currency": self._currency,
            "resolution": self.coordinator.resolution,
            "use_subunits": self.use_subunits,
            "timeline_data": timeline_data,
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
            }
        }
        
        return attrs
