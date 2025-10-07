"""Config flow for Tibber Extended."""
import logging
import voluptuous as vol
import aiohttp
import re

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_RESOLUTION,
    CONF_UPDATE_TIMES,
    CONF_HOME_NAME,
    DEFAULT_DEMO_TOKEN,
    DEFAULT_UPDATE_TIMES,
    RESOLUTION_OPTIONS,
    TIBBER_API_URL,
)

_LOGGER = logging.getLogger(__name__)


def validate_time_format(time_str: str) -> bool:
    """Validate time format HH:MM."""
    pattern = r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$'
    return bool(re.match(pattern, time_str))


class TibberExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber Extended."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the token
            token = user_input.get(CONF_ACCESS_TOKEN, "").strip()
            
            # Om användaren lämnade tomt, använd demo token
            if not token:
                token = DEFAULT_DEMO_TOKEN
                user_input[CONF_ACCESS_TOKEN] = token
            
            # Validera update_times format
            update_times_str = user_input.get(CONF_UPDATE_TIMES, "")
            times_list = [t.strip() for t in update_times_str.split(",") if t.strip()]
            
            valid_times = True
            for time_str in times_list:
                if not validate_time_format(time_str):
                    valid_times = False
                    errors["base"] = "invalid_time_format"
                    break
            
            if valid_times:
                # Validera token
                valid = await self._validate_token(token)
                
                if valid:
                    # Spara times_list istället för sträng
                    user_input[CONF_UPDATE_TIMES] = times_list if times_list else DEFAULT_UPDATE_TIMES
                    
                    return self.async_create_entry(
                        title=user_input.get(CONF_HOME_NAME, "Tibber Extended"),
                        data=user_input,
                    )
                else:
                    errors["base"] = "invalid_token"

        # Skapa default värden
        default_times = ", ".join(DEFAULT_UPDATE_TIMES)
        
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ACCESS_TOKEN,
                    description={"suggested_value": ""},
                ): str,
                vol.Optional(
                    CONF_HOME_NAME,
                    default="Mitt Hem"
                ): str,
                vol.Optional(
                    CONF_RESOLUTION, 
                    default="QUARTER_HOURLY"
                ): vol.In(RESOLUTION_OPTIONS),
                vol.Optional(
                    CONF_UPDATE_TIMES,
                    default=default_times
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "demo_token_info": "Lämna tomt för att använda Tibbers demo-token (kan sluta fungera)",
                "time_format": "Ange tider separerade med komma, t.ex: 13:00, 15:00, 20:00",
            }
        )

    async def _validate_token(self, token: str) -> bool:
        """Validate the Tibber API token."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        query = """
        {
            viewer {
                homes {
                    id
                }
            }
        }
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TIBBER_API_URL,
                    json={"query": query},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return "errors" not in data
        except Exception as err:
            _LOGGER.error("Error validating token: %s", err)
        
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TibberExtendedOptionsFlow(config_entry)


class TibberExtendedOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Tibber Extended."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        errors = {}
        
        if user_input is not None:
            # Validera token om angiven
            token = user_input.get(CONF_ACCESS_TOKEN, "").strip()
            if not token:
                token = self._config_entry.data.get(CONF_ACCESS_TOKEN, DEFAULT_DEMO_TOKEN)
            
            # Validera update_times format
            update_times_str = user_input.get(CONF_UPDATE_TIMES, "")
            times_list = [t.strip() for t in update_times_str.split(",") if t.strip()]
            
            valid_times = True
            for time_str in times_list:
                if not validate_time_format(time_str):
                    valid_times = False
                    errors["base"] = "invalid_time_format"
                    break
            
            if valid_times:
                # Validera token
                valid = await self._validate_token(token)
                
                if valid:
                    user_input[CONF_UPDATE_TIMES] = times_list if times_list else DEFAULT_UPDATE_TIMES
                    user_input[CONF_ACCESS_TOKEN] = token
                    
                    # Uppdatera config entry data
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data={**self._config_entry.data, **user_input}
                    )
                    
                    return self.async_create_entry(title="", data={})
                else:
                    errors["base"] = "invalid_token"

        # Hämta nuvarande värden
        current_times = self._config_entry.data.get(CONF_UPDATE_TIMES, DEFAULT_UPDATE_TIMES)
        if isinstance(current_times, list):
            current_times_str = ", ".join(current_times)
        else:
            current_times_str = current_times

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ACCESS_TOKEN,
                    description={"suggested_value": ""},
                ): str,
                vol.Optional(
                    CONF_HOME_NAME,
                    default=self._config_entry.data.get(CONF_HOME_NAME, "Mitt Hem"),
                ): str,
                vol.Optional(
                    CONF_RESOLUTION,
                    default=self._config_entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY"),
                ): vol.In(RESOLUTION_OPTIONS),
                vol.Optional(
                    CONF_UPDATE_TIMES,
                    default=current_times_str,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init", 
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "time_format": "Ange tider separerade med komma, t.ex: 13:00, 15:00, 20:00",
                "token_info": "Lämna tomt för att behålla nuvarande token",
            }
        )

    async def _validate_token(self, token: str) -> bool:
        """Validate the Tibber API token."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        query = """
        {
            viewer {
                homes {
                    id
                }
            }
        }
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TIBBER_API_URL,
                    json={"query": query},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return "errors" not in data
        except Exception as err:
            _LOGGER.error("Error validating token: %s", err)
        
        return False