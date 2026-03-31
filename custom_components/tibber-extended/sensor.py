"""Sensor platform for Tibber Extended."""
import asyncio
import logging
import random
from datetime import time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.const import EntityCategory

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CURRENCY,
    CONF_HOME_NAME,
    CONF_RESOLUTION,
    DEFAULT_CURRENCY,
    DEFAULT_UPDATE_TIMES,
    DOMAIN,
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

    # Läs in cachad data från disk INNAN första uppdateringen
    await coordinator.async_load_from_storage()

    # Försök hämta data första gången
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data: %s", err)

    home_name = entry.data.get(CONF_HOME_NAME, "Mitt Hem")
    currency = entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
    entities = []

    # Skapa sensorer för varje hem
    if coordinator.data:
        for home_id, home_data in coordinator.data.items():
            _LOGGER.info(f"Creating sensors for home: {home_id}")
            # Huvud-prissensor
            entities.append(TibberPriceSensor(coordinator, home_id, home_name, currency))

            # Elnätsbolag
            entities.append(TibberDetailsSensor(coordinator, home_id, home_name, "grid_company", "Grid Company", "mdi:transmission-tower"))

            # Månadsförbrukning (Energi & Kostnad separat)
            entities.append(TibberEnergyConsumptionSensor(coordinator, home_id, home_name))
            entities.append(TibberCostConsumptionSensor(coordinator, home_id, home_name))
    else:
        _LOGGER.warning("No data available yet, creating basic sensor anyway")
        entities.append(TibberPriceSensor(coordinator, "pending", home_name, currency))

    async_add_entities(entities, True)
    _LOGGER.info(f"Added {len(entities)} Tibber sensors (including metadata)")


class TibberDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tibber data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.token = entry.data[CONF_ACCESS_TOKEN]
        self.resolution = entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY")
        # Hårdkoda uppdateringstider till 13, 14, 15 (ignorerar gammal config)
        self.update_times = DEFAULT_UPDATE_TIMES
        self.entry = entry
        self._last_midnight_shift = None  # Håll koll på när vi senast flyttade data
        self._force_update = False  # Flagga för att tvinga fram API-anrop (bypass cache)
        self._home_timezones = {}  # Tidszon per hem, hämtas från API

        # Konvertera update_times till time-objekt
        self.update_times_parsed = []
        for time_str in self.update_times:
            try:
                hour, minute = map(int, time_str.split(":"))
                self.update_times_parsed.append(time(hour=hour, minute=minute))
            except ValueError:
                _LOGGER.error(f"Invalid time format: {time_str}")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )

        # Persistent lagring
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")

        self._setup_time_triggers()

    async def async_load_from_storage(self):
        """Load cached data from storage."""
        try:
            cached_data = await self._store.async_load()
            if cached_data:
                self.data = cached_data
                _LOGGER.info(f"Loaded {len(cached_data)} homes from persistent storage")
        except Exception as err:
            _LOGGER.error(f"Failed to load data from storage: {err}")

    async def async_save_to_storage(self):
        """Save current data to storage."""
        try:
            await self._store.async_save(self.data)
            _LOGGER.debug("Data saved to persistent storage")
        except Exception as err:
            _LOGGER.error(f"Failed to save data to storage: {err}")

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
        # Lägg till korta slumpmässiga fördröjningar (jitter) för att undvika rate limiting
        delay = random.uniform(1, 60)
        _LOGGER.info(
            f"Time trigger fired at {now}, waiting {delay:.1f}s jitter before fetching Tibber data"
        )
        await asyncio.sleep(delay)
        await self.async_request_refresh()

    async def _handle_midnight_shift(self, now):
        """Shift tomorrow prices to today at midnight."""
        current_date = now.date()

        if self._last_midnight_shift == current_date:
            _LOGGER.debug("Midnight shift already performed today")
            return

        if not self.data:
            _LOGGER.warning("No data to shift at midnight")
            return

        for home_id in self.data.keys():
            tomorrow_prices = self.data[home_id].get("tomorrow", [])
            if tomorrow_prices:
                _LOGGER.info(f"Shifting prices for home {home_id}")
                self.data[home_id]["today"] = tomorrow_prices
                self.data[home_id]["tomorrow"] = []

        self._last_midnight_shift = current_date
        self.async_set_updated_data(self.data)
        _LOGGER.info("Midnight shift completed")

    def _now_in_home_tz(self, home_id=None):
        """Get current time in the home's timezone."""
        tz_name = None
        if home_id:
            tz_name = self._home_timezones.get(home_id)
        elif self._home_timezones:
            tz_name = next(iter(self._home_timezones.values()))

        if tz_name:
            try:
                return dt_util.now().astimezone(ZoneInfo(tz_name))
            except (ZoneInfoNotFoundError, Exception) as err:
                _LOGGER.warning(f"Invalid timezone '{tz_name}', falling back to local: {err}")
        return dt_util.now()

    async def _async_update_data(self):
        """Fetch data from Tibber API."""
        now = self._now_in_home_tz()
        now_time = now.time()
        fetch_tomorrow = now_time >= time(12, 45)

        # SMART CACHING
        if self.data and not self._force_update:
            all_homes_have_data = True
            for home_id in self.data:
                home_data = self.data[home_id]
                if not home_data.get("today"):
                    all_homes_have_data = False
                    break
                if fetch_tomorrow and not home_data.get("tomorrow"):
                    all_homes_have_data = False
                    break

            if all_homes_have_data:
                _LOGGER.debug("Smart Caching: Already have required price data")
                # Spara till storage för säkerhets skull (vid ev. manuell ändring i minnet)
                await self.async_save_to_storage()
                return self.data

        # Återställ flaggan inför anropet
        self._force_update = False

        _LOGGER.debug(f"Fetching data (tomorrow: {fetch_tomorrow})")

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
                    timeZone
                    meteringPointData {
                        gridCompany
                    }
                    consumption(resolution: DAILY, last: 31) {
                        nodes {
                            from
                            to
                            cost
                            consumption
                        }
                    }
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
            "User-Agent": "HomeAssistant/Tibber-Extended (1.2.3)",
        }

        max_attempts = 3
        session = async_get_clientsession(self.hass)

        for attempt in range(max_attempts):
            try:
                async with session.post(
                    TIBBER_API_URL,
                    json={"query": query},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        _LOGGER.warning(f"Rate limited (429). Waiting {retry_after}s.")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        raise UpdateFailed("Rate limited by Tibber")

                    if response.status != 200:
                        if response.status in [500, 502, 503, 504] and attempt < max_attempts - 1:
                            wait_time = (2 ** attempt) + random.uniform(0.1, 1.0)
                            _LOGGER.warning(f"Server error {response.status}. Retry {attempt+1} in {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        raise UpdateFailed(f"API error: {response.status}")

                    data = await response.json()
                    if "errors" in data:
                        error_msg = data['errors'][0].get('message', 'Unknown error')
                        _LOGGER.error(f"GraphQL error: {error_msg}")
                        raise UpdateFailed(f"GraphQL error: {error_msg}")

                    homes_data = {}
                    viewer_data = data.get("data", {}).get("viewer", {})
                    homes = viewer_data.get("homes", [])

                    for home in homes:
                        home_id = home["id"]
                        sub = home.get("currentSubscription")
                        if not sub:
                            continue

                        # Spara tidszon från API
                        home_tz = home.get("timeZone")
                        if home_tz:
                            self._home_timezones[home_id] = home_tz
                            _LOGGER.debug(f"Home {home_id} timezone: {home_tz}")

                        price_info = sub.get("priceInfo", {})
                        existing_tomorrow = []
                        if self.data and home_id in self.data:
                            existing_tomorrow = self.data[home_id].get("tomorrow", [])

                        homes_data[home_id] = {
                            "name": home.get("appNickname", "Home"),
                            "today": price_info.get("today", []),
                            "tomorrow": price_info.get("tomorrow", existing_tomorrow),
                            "consumption": home.get("consumption", {}).get("nodes", []),
                            "metadata": {
                                "grid_company": (home.get("meteringPointData") or {}).get("gridCompany"),
                            }
                        }

                    _LOGGER.info(f"Fetched Tibber data for {len(homes_data)} home(s)")
                    self.data = homes_data
                    await self.async_save_to_storage()
                    return homes_data

            except asyncio.TimeoutError:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise UpdateFailed("Timeout from Tibber API")
            except Exception as err:
                _LOGGER.error(f"Unexpected error: {err}")
                raise UpdateFailed(f"Error: {err}")


class TibberPriceSensor(CoordinatorEntity, SensorEntity):
    """Unified sensor for Tibber electricity prices."""

    def __init__(self, coordinator, home_id, home_name, currency):
        """Initialize."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._home_name = home_name
        self._currency = currency
        self._attr_name = f"{home_name} Electricity Price"
        self._attr_unique_id = f"{home_id}_electricity_price"

        self.use_subunits = coordinator.entry.options.get(
            "use_subunits", coordinator.entry.data.get("use_subunits", False)
        )

        from .utils import get_unit_label
        self._attr_native_unit_of_measurement = get_unit_label(currency, self.use_subunits)
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:flash"
        self._update_listeners = []

    async def async_added_to_hass(self):
        """When added."""
        await super().async_added_to_hass()
        minutes = [0, 15, 30, 45] if self.coordinator.resolution == "QUARTER_HOURLY" else [0]
        for minute in minutes:
            self._update_listeners.append(
                async_track_time_change(self.hass, self._update_state, minute=minute, second=1)
            )

    async def async_will_remove_from_hass(self):
        """When removed."""
        await super().async_will_remove_from_hass()
        for remover in self._update_listeners:
            remover()
        self._update_listeners = []

    async def _update_state(self, now=None):
        """Update."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return availability."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        if self._home_id == "pending" and self.coordinator.data:
            self._home_id = list(self.coordinator.data.keys())[0]
            self._attr_unique_id = f"{self._home_id}_electricity_price"
        return bool(self._home_id in self.coordinator.data)

    def _get_current_price_point(self):
        """Get current data using home timezone."""
        if not self.available:
            return None
        now = self.coordinator._now_in_home_tz(self._home_id)
        today_prices = self.coordinator.data[self._home_id]["today"]
        for p in today_prices:
            st = dt_util.parse_datetime(p["startsAt"])
            if not st:
                continue
            # Konvertera till hemmets tidszon för korrekt jämförelse
            home_tz_name = self.coordinator._home_timezones.get(self._home_id)
            if home_tz_name:
                try:
                    st = st.astimezone(ZoneInfo(home_tz_name))
                except (ZoneInfoNotFoundError, Exception):
                    pass
            interval = 15 if self.coordinator.resolution == "QUARTER_HOURLY" else 60
            if st <= now < st + timedelta(minutes=interval):
                return p
        return None

    @property
    def native_value(self):
        """Return value."""
        p = self._get_current_price_point()
        return format_price_value(p.get("total", 0), self.use_subunits) if p else None

    @property
    def icon(self):
        """Return icon."""
        p = self._get_current_price_point()
        if p:
            level = p.get("level", "UNKNOWN")
            mapping = {"VERY_CHEAP": "mdi:arrow-down-bold", "CHEAP": "mdi:arrow-down",
                       "NORMAL": "mdi:minus", "EXPENSIVE": "mdi:arrow-up",
                       "VERY_EXPENSIVE": "mdi:arrow-up-bold"}
            return mapping.get(level, "mdi:flash")
        return "mdi:flash"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        if not self.available:
            return {}

        home_data = self.coordinator.data[self._home_id]
        today_prices = home_data["today"]
        tomorrow_prices = home_data["tomorrow"]
        p = self._get_current_price_point()

        def calc(prices, field):
            vals = [pt.get(field, 0) for pt in prices if field in pt]
            if not vals:
                return {}
            return {
                "min": format_price_value(min(vals), self.use_subunits),
                "max": format_price_value(max(vals), self.use_subunits),
                "avg": format_price_value(sum(vals) / len(vals), self.use_subunits),
            }

        current_total = p.get("total") if p else None
        current_energy = p.get("energy") if p else None
        current_tax = p.get("tax") if p else None

        data = [
            {
                "start_time": pt["startsAt"],
                "price_per_kwh": format_price_value(pt["total"], self.use_subunits),
            }
            for pt in today_prices + tomorrow_prices
        ]

        return {
            "current_total": format_price_value(current_total, self.use_subunits),
            "current_energy": format_price_value(current_energy, self.use_subunits),
            "current_tax": format_price_value(current_tax, self.use_subunits),
            "current_level": p.get("level", "UNKNOWN") if p else "UNKNOWN",
            "current_starts_at": p.get("startsAt") if p else None,
            "currency": self._currency,
            "resolution": self.coordinator.resolution,
            "home_timezone": self.coordinator._home_timezones.get(self._home_id, "unknown"),
            "use_subunits": self.use_subunits,
            "data": data,
            "today": {
                "prices": today_prices,
                "total": calc(today_prices, "total"),
                "energy": calc(today_prices, "energy"),
            },
            "tomorrow": {
                "prices": tomorrow_prices,
                "total": calc(tomorrow_prices, "total"),
                "energy": calc(tomorrow_prices, "energy"),
            },
        }


class TibberEnergyConsumptionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for monthly electricity consumption (kWh)."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._attr_name = f"{home_name} Monthly Consumption"
        self._attr_unique_id = f"{home_id}_monthly_consumption"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_icon = "mdi:counter"

    @property
    def available(self) -> bool:
        """Return availability."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.data
            and self._home_id in self.coordinator.data
        )

    def _get_monthly_energy(self):
        """Calculate consumption (kWh) for the current month."""
        if not self.available:
            return 0.0

        nodes = self.coordinator.data[self._home_id].get("consumption", [])
        if not nodes:
            return 0.0

        now = self.coordinator._now_in_home_tz(self._home_id)
        current_month = now.month
        current_year = now.year

        total_consumption = 0.0
        for node in nodes:
            from_dt = dt_util.parse_datetime(node["from"])
            if not from_dt:
                continue
            if from_dt.month == current_month and from_dt.year == current_year:
                total_consumption += node.get("consumption") or 0.0

        return round(total_consumption, 2)

    @property
    def native_value(self):
        """Return the total consumption for the current month."""
        return self._get_monthly_energy()

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {
            "data_delay_info": "Consumption data is typically delayed 24-48h by the grid company."
        }


class TibberCostConsumptionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for monthly electricity cost."""

    def __init__(self, coordinator, home_id, home_name):
        """Initialize."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._attr_name = f"{home_name} Monthly Cost"
        self._attr_unique_id = f"{home_id}_monthly_cost"

        currency = coordinator.entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        from .utils import get_unit_label
        # Vi använder basenheten (kr/EUR) för total månadskostnad, oavsett subunit-inställning
        self._attr_native_unit_of_measurement = get_unit_label(currency, False).split("/")[0]

        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_icon = "mdi:cash"

    @property
    def available(self) -> bool:
        """Return availability."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.data
            and self._home_id in self.coordinator.data
        )

    def _get_monthly_cost(self):
        """Calculate cost for the current month."""
        if not self.available:
            return 0.0

        nodes = self.coordinator.data[self._home_id].get("consumption", [])
        if not nodes:
            return 0.0

        now = self.coordinator._now_in_home_tz(self._home_id)
        current_month = now.month
        current_year = now.year

        total_cost = 0.0
        for node in nodes:
            from_dt = dt_util.parse_datetime(node["from"])
            if not from_dt:
                continue
            if from_dt.month == current_month and from_dt.year == current_year:
                total_cost += node.get("cost") or 0.0

        return round(total_cost, 2)

    @property
    def native_value(self):
        """Return the total cost for the current month."""
        return self._get_monthly_cost()

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        currency = self.coordinator.entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        return {
            "currency": currency,
            "data_delay_info": "Cost data is typically delayed 24-48h by the grid company."
        }


class TibberDetailsSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for Tibber home metadata."""

    def __init__(self, coordinator, home_id, home_name, key, label, icon):
        """Initialize."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._key = key
        self._attr_name = f"{home_name} {label}"
        self._attr_unique_id = f"{home_id}_{key}"
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        """Return availability."""
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.data
            and self._home_id in self.coordinator.data
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.available:
            return None
        metadata = self.coordinator.data[self._home_id].get("metadata", {})
        return metadata.get(self._key)

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return {}
