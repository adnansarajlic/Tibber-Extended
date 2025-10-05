"""Constants for Tibber Extended."""

DOMAIN = "tibber_extended"

CONF_ACCESS_TOKEN = "access_token"
CONF_RESOLUTION = "resolution"
CONF_UPDATE_HOUR = "update_hour"
CONF_UPDATE_MINUTE = "update_minute"

DEFAULT_UPDATE_HOUR = 15
DEFAULT_UPDATE_MINUTE = 0

RESOLUTION_OPTIONS = {
    "HOURLY": "Hourly",
    "QUARTER_HOURLY": "Quarter Hourly (15 min)",
}

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"