"""Button platform for Tibber Extended."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_HOME_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Extended button."""
    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    except KeyError:
        _LOGGER.error("Coordinator inte hittad, kan inte ladda knappen")
        return

    home_name = entry.data.get(CONF_HOME_NAME, "Mitt Hem")

    async_add_entities([
        TibberRefreshButton(coordinator, home_name),
        TibberRecalculateBestPriceButton(coordinator, home_name)
    ], True)
    _LOGGER.info("Successfully setup Tibber refresh button")


class TibberRefreshButton(ButtonEntity):
    """Button to trigger manual refresh of Tibber prices."""

    def __init__(self, coordinator, home_name):
        """Initialize the button."""
        self.coordinator = coordinator
        self._attr_name = f"{home_name} Update Prices"
        self._attr_unique_id = f"tibber_extended_refresh_{coordinator.entry.entry_id}"
        self._attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manuell uppdatering begärd via Refresh-knapp (Bypassar Smart Caching)")
        self.coordinator._force_update = True
        await self.coordinator.async_request_refresh()


class TibberRecalculateBestPriceButton(ButtonEntity):
    """Button to trigger manual recalculation of Best Price windows."""

    def __init__(self, coordinator, home_name):
        """Initialize the button."""
        self.coordinator = coordinator
        self._attr_name = f"{home_name} Re-calculate Best Price"
        self._attr_unique_id = f"tibber_extended_recalc_{coordinator.entry.entry_id}"
        self._attr_icon = "mdi:calculator"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Manuell omräkning av Best Price begärd via Re-calculate-knapp")
        orig_force = getattr(self.coordinator, "_force_update", False)
        self.coordinator._force_update = True
        try:
            # Triggar uppdatering för alla listeners (bypassar tidslås och exkluderar passerade priser)
            self.coordinator.async_set_updated_data(self.coordinator.data)
        finally:
            self.coordinator._force_update = orig_force
