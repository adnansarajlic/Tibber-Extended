"""Tester för config_flow.py."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from tibber_extended.config_flow import TibberExtendedOptionsFlow
from tibber_extended.const import (
    CONF_ACCESS_TOKEN,
    CONF_RESTRICT_TIME_START,
    CONF_RESTRICT_TIME_END,
    CONF_BEST_PRICE_SPANS,
)


@pytest.mark.asyncio
async def test_options_flow_clears_empty_fields():
    """Om användaren tömmer tidsrestriktioner i formuläret ska config uppdateras med tomma strängar."""
    
    # Skapa mock för config entry (befintlig konfig)
    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_ACCESS_TOKEN: "valid_token",
        CONF_RESTRICT_TIME_START: "22:00",
        CONF_RESTRICT_TIME_END: "06:00",
        CONF_BEST_PRICE_SPANS: "1, 2, 3",
    }
    
    # Initialisera options flow
    flow = TibberExtendedOptionsFlow(mock_entry)
    flow.hass = MagicMock()
    
    # Mocka token-validering att alltid returnera True
    flow._validate_token = AsyncMock(return_value=True)

    # Scenariot: Användaren skickar in formuläret men raderar restriktion-raderna.
    # I HA-formulär rensas fälten helt från 'user_input' dict:en.
    user_input = {
        CONF_ACCESS_TOKEN: "valid_token"
        # Notera: Inga restrict_time-fält närvarande, simulering av tömt formulär
    }

    result = await flow.async_step_init(user_input=user_input)
    assert result["type"] == "create_entry"
    
    # Kontrollera vad som HA sparar. '_config_entry.data' MÅSTE ha tomma strängar
    call_kwargs = flow.hass.config_entries.async_update_entry.call_args.kwargs
    new_data = call_kwargs["data"]

    # Dessa fält var raderade, och BUG FIXEN ska säkerställa att de blev ""
    assert new_data[CONF_RESTRICT_TIME_START] == ""
    assert new_data[CONF_RESTRICT_TIME_END] == ""
    assert new_data[CONF_BEST_PRICE_SPANS] == ""
