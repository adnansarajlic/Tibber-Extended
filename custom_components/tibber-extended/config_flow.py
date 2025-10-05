import logging
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_RESOLUTION,
    CONF_UPDATE_HOUR,
    CONF_UPDATE_MINUTE,
    DEFAULT_UPDATE_HOUR,
    DEFAULT_UPDATE_MINUTE,
    RESOLUTION_OPTIONS,
    TIBBER_API_URL,
)

_LOGGER = logging.getLogger(__name__)


class TibberExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber Extended."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the token
            valid = await self._validate_token(user_input[CONF_ACCESS_TOKEN])
            
            if valid:
                return self.async_create_entry(
                    title="Tibber Extended",
                    data=user_input,
                )
            else:
                errors["base"] = "invalid_token"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): str,
                vol.Optional(
                    CONF_RESOLUTION, 
                    default="QUARTER_HOURLY"
                ): vol.In(RESOLUTION_OPTIONS),
                vol.Optional(
                    CONF_UPDATE_HOUR, 
                    default=DEFAULT_UPDATE_HOUR
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_UPDATE_MINUTE, 
                    default=DEFAULT_UPDATE_MINUTE
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RESOLUTION,
                    default=self.config_entry.data.get(CONF_RESOLUTION, "QUARTER_HOURLY"),
                ): vol.In(RESOLUTION_OPTIONS),
                vol.Optional(
                    CONF_UPDATE_HOUR,
                    default=self.config_entry.data.get(CONF_UPDATE_HOUR, DEFAULT_UPDATE_HOUR),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_UPDATE_MINUTE,
                    default=self.config_entry.data.get(CONF_UPDATE_MINUTE, DEFAULT_UPDATE_MINUTE),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)