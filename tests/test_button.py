"""Tester för button.py och konfigurering."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from tibber_extended.button import (
    async_setup_entry,
    TibberRefreshButton,
    TibberRecalculateBestPriceButton,
)
from tibber_extended.const import (
    DOMAIN,
    CONF_HOME_NAME,
    CONF_ACCESS_TOKEN,
    CONF_RECALCULATE_ON_SAVE,
    CONF_RESTRICT_TIME_START,
)
from tibber_extended.config_flow import TibberExtendedOptionsFlow


@pytest.fixture
def mock_coordinator():
    """Skapa en mock för koordinatorn."""
    coordinator = MagicMock()
    coordinator.entry = MagicMock()
    coordinator.entry.entry_id = "test_entry_id"
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    coordinator.data = {"test": "data"}
    coordinator._force_update = False
    return coordinator


@pytest.mark.asyncio
async def test_setup_button_platform(mock_coordinator):
    """Testa plattformens setup-funktion."""
    mock_hass = MagicMock()
    mock_hass.data = {DOMAIN: {"test_entry_id": {"coordinator": mock_coordinator}}}

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {CONF_HOME_NAME: "Test Hem"}

    async_add_entities = MagicMock()

    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    # Verifiera att knappen lades till
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    # Vi kollar klassnamn för att undvika isinstance-strul med olika modulladdningar
    assert entities[0].__class__.__name__ == "TibberRefreshButton"
    assert entities[1].__class__.__name__ == "TibberRecalculateBestPriceButton"


@pytest.mark.asyncio
async def test_refresh_button_press(mock_coordinator):
    """Testa att Refresh-knappen anropar koordinatorns refresh."""
    button = TibberRefreshButton(mock_coordinator, "Test Hem")
    mock_coordinator.async_request_refresh.return_value = None
    await button.async_press()
    assert mock_coordinator._force_update is True
    assert mock_coordinator.async_request_refresh.called


@pytest.mark.asyncio
async def test_recalculate_button_press(mock_coordinator):
    """Testa att Recalculate-knappen pushar data internt."""
    button = TibberRecalculateBestPriceButton(mock_coordinator, "Test Hem")
    mock_coordinator._force_update = False
    await button.async_press()
    mock_coordinator.async_set_updated_data.assert_called_once_with({"test": "data"})
    assert mock_coordinator._force_update is False


@pytest.mark.asyncio
async def test_options_flow_sets_recalculate_flag():
    """Testa att valet 'recalculate_on_save' sätter en tillfällig flagga i hass.data."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {CONF_ACCESS_TOKEN: "valid_token"}

    flow = TibberExtendedOptionsFlow(mock_entry)
    flow.hass = MagicMock()
    flow.hass.data = {}

    # Mocka token-validering
    flow._validate_token = AsyncMock(return_value=True)

    user_input = {
        CONF_ACCESS_TOKEN: "valid_token",
        CONF_RECALCULATE_ON_SAVE: True,
        CONF_RESTRICT_TIME_START: "23:00"
    }

    await flow.async_step_init(user_input=user_input)

    # Kontrollera att flaggan sattes i hass.data
    # Eftersom vi använder 'tibber_extended_flags' i koden:
    assert flow.hass.data["tibber_extended_flags"]["force_recalc_test_entry_id"] is True
