"""Constants for Tibber Extended."""

DOMAIN = "tibber_extended"

CONF_ACCESS_TOKEN = "access_token"
CONF_RESOLUTION = "resolution"
CONF_UPDATE_TIMES = "update_times"
CONF_HOME_NAME = "home_name"

# Tibber Demo Token - fungerar för testning men kan sluta fungera när som helst
DEFAULT_DEMO_TOKEN = "3A77EECF61BD445F47241A5A36202185C35AF3AF58609E19B53F3A8872AD7BE1-1"

# Default uppdateringstider (kl 13:00 och 15:00)
DEFAULT_UPDATE_TIMES = ["13:00", "15:00"]

RESOLUTION_OPTIONS = {
    "HOURLY": "Hourly",
    "QUARTER_HOURLY": "Quarter Hourly (15 min)",
}

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"

# Test query for token validation
TEST_QUERY = """
{
    viewer {
        name
        homes {
            id
            appNickname
        }
    }
}
"""