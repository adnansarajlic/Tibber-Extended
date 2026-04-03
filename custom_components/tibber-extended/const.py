"""Constants for Tibber Extended."""

DOMAIN = "tibber_extended"

CONF_ACCESS_TOKEN = "access_token"
CONF_RESOLUTION = "resolution"
CONF_UPDATE_TIMES = "update_times"
CONF_HOME_NAME = "home_name"
CONF_CURRENCY = "currency"

# Tibber Demo Token - fungerar för testning men kan sluta fungera när som helst
DEFAULT_DEMO_TOKEN = "3A77EECF61BD445F47241A5A36202185C35AF3AF58609E19B53F3A8872AD7BE1-1"

# Binary Sensor Target Hours
CONF_BEST_PRICE_TARGET_HOURS = "best_price_target_hours"
CONF_BEST_PRICE_SPANS = "best_price_spans"
CONF_PEAK_PRICE_TARGET_HOURS = "peak_price_target_hours"
DEFAULT_BEST_PRICE_TARGET_HOURS = 3.0
DEFAULT_PEAK_PRICE_TARGET_HOURS = 3.0
DEFAULT_BEST_PRICE_SPANS = "3.0"

# Price Threshold Sensor
CONF_PRICE_THRESHOLD = "price_threshold"
DEFAULT_PRICE_THRESHOLD = 0.50

# Recalculate Option
CONF_RECALCULATE_ON_SAVE = "recalculate_on_save"
DEFAULT_RECALCULATE_ON_SAVE = False

# Optional Time Restrictions
CONF_RESTRICT_TIME_START = "restrict_time_start"
CONF_RESTRICT_TIME_END = "restrict_time_end"
DEFAULT_RESTRICT_TIME_START = ""
DEFAULT_RESTRICT_TIME_END = ""

# Subunits setup
CONF_USE_SUBUNITS = "use_subunits"
DEFAULT_USE_SUBUNITS = False

# Default uppdateringstider (kl 13:00, 14:00 och 15:00)
DEFAULT_UPDATE_TIMES = ["13:00", "14:00", "15:00"]

# Default valuta
DEFAULT_CURRENCY = "SEK"

RESOLUTION_OPTIONS = {
    "HOURLY": "Hourly",
    "QUARTER_HOURLY": "Quarter Hourly (15 min)",
}

CURRENCY_OPTIONS = {
    "SEK": "SEK (Swedish Krona)",
    "NOK": "NOK (Norwegian Krone)",
    "EUR": "EUR (Euro)",
    "DKK": "DKK (Danish Krone)",
}

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
