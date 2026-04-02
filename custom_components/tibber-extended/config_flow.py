"""Config flow for Tibber Extended."""
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
    CONF_HOME_NAME,
    CONF_CURRENCY,
    DEFAULT_DEMO_TOKEN,
    DEFAULT_CURRENCY,
    RESOLUTION_OPTIONS,
    CURRENCY_OPTIONS,
    TIBBER_API_URL,
    CONF_PEAK_PRICE_TARGET_HOURS,
    CONF_BEST_PRICE_SPANS,
    DEFAULT_PEAK_PRICE_TARGET_HOURS,
    DEFAULT_BEST_PRICE_SPANS,
    CONF_USE_SUBUNITS,
    DEFAULT_USE_SUBUNITS,
    CONF_RESTRICT_TIME_START,
    CONF_RESTRICT_TIME_END,
    DEFAULT_RESTRICT_TIME_START,
    DEFAULT_RESTRICT_TIME_END,
    CONF_PRICE_THRESHOLD,
    DEFAULT_PRICE_THRESHOLD,
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
            token = user_input.get(CONF_ACCESS_TOKEN, "").strip()

            # Om användaren lämnade tomt, använd demo token
            if not token:
                token = DEFAULT_DEMO_TOKEN
                user_input[CONF_ACCESS_TOKEN] = token

            # Validera token
            valid = await self._validate_token(token)

            if valid:
                return self.async_create_entry(
                    title=user_input.get(CONF_HOME_NAME, "Tibber Extended"),
                    data=user_input,
                )
            else:
                errors["base"] = "invalid_token"

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
                vol.Required(
                    CONF_CURRENCY,
                    default=DEFAULT_CURRENCY
                ): vol.In(CURRENCY_OPTIONS),
                vol.Optional(
                    CONF_USE_SUBUNITS,
                    default=DEFAULT_USE_SUBUNITS,
                ): bool,
                vol.Optional(
                    CONF_BEST_PRICE_SPANS,
                    default=DEFAULT_BEST_PRICE_SPANS,
                ): str,
                vol.Optional(
                    CONF_PEAK_PRICE_TARGET_HOURS,
                    default=str(DEFAULT_PEAK_PRICE_TARGET_HOURS),
                ): vol.In(["0.5", "1.0", "1.5", "2.0", "3.0", "4.0", "6.0"]),
                vol.Optional(
                    CONF_PRICE_THRESHOLD,
                    default=DEFAULT_PRICE_THRESHOLD,
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_RESTRICT_TIME_START,
                    description={"suggested_value": DEFAULT_RESTRICT_TIME_START},
                ): str,
                vol.Optional(
                    CONF_RESTRICT_TIME_END,
                    description={"suggested_value": DEFAULT_RESTRICT_TIME_END},
                ): str,
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
                    timeout=aiohttp.ClientTimeout(total=30),
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

            # Validera token
            valid = await self._validate_token(token)

            if valid:
                user_input[CONF_ACCESS_TOKEN] = token

                # Sätt värden till tomma strängar om användaren raderat dem
                for key in (CONF_RESTRICT_TIME_START, CONF_RESTRICT_TIME_END, CONF_BEST_PRICE_SPANS):
                    if key not in user_input:
                        user_input[key] = ""

                # Uppdatera config entry data
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={**self._config_entry.data, **user_input}
                )

                return self.async_create_entry(title="", data={})
            else:
                errors["base"] = "invalid_token"

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
                vol.Required(
                    CONF_CURRENCY,
                    default=self._config_entry.data.get(
                        CONF_CURRENCY, DEFAULT_CURRENCY
                    ),
                ): vol.In(CURRENCY_OPTIONS),
                vol.Optional(
                    CONF_USE_SUBUNITS,
                    default=self._config_entry.data.get(
                        CONF_USE_SUBUNITS, DEFAULT_USE_SUBUNITS
                    ),
                ): bool,
                vol.Optional(
                    CONF_BEST_PRICE_SPANS,
                    default=self._config_entry.data.get(CONF_BEST_PRICE_SPANS, DEFAULT_BEST_PRICE_SPANS),
                ): str,
                vol.Optional(
                    CONF_PEAK_PRICE_TARGET_HOURS,
                    default=str(self._config_entry.data.get(CONF_PEAK_PRICE_TARGET_HOURS, DEFAULT_PEAK_PRICE_TARGET_HOURS)),
                ): vol.In(["0.5", "1.0", "1.5", "2.0", "3.0", "4.0", "6.0"]),
                vol.Optional(
                    CONF_PRICE_THRESHOLD,
                    default=self._config_entry.data.get(CONF_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_RESTRICT_TIME_START,
                    description={"suggested_value": self._config_entry.data.get(CONF_RESTRICT_TIME_START, DEFAULT_RESTRICT_TIME_START)},
                ): str,
                vol.Optional(
                    CONF_RESTRICT_TIME_END,
                    description={"suggested_value": self._config_entry.data.get(CONF_RESTRICT_TIME_END, DEFAULT_RESTRICT_TIME_END)},
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
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
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return "errors" not in data
        except Exception as err:
            _LOGGER.error("Error validating token: %s", err)

        return False
