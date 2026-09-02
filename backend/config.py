"""App configuration and constants."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# OpenRouter endpoint (using OpenAI-compatible client)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or OPENAI_API_KEY
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# Fallback model when primary is overloaded or returns empty
FALLBACK_MODEL = "openai/gpt-4o-mini"

# Departure address
HOME_ADDRESS = "Heirweg 85A, 9190 Stekene, Belgium"

# EV constants
CHARGE_UP_TO_PERCENT = 90.0
AVERAGE_SPEED_KMPH = 80.0
CHARGING_TIME_MINUTES = 45.0
SEARCH_RADIUS_METERS = 2000
MAX_RESULTS_TO_PROCESS = 5
BATTERY_CAPACITY_KWH = 78.0
CONSUMPTION_KWH_PER_100KM = 17.31

# Hotel search
HOTEL_SEARCH_RADIUS = 1500  # meters from city center
HOTEL_DISTANCE_LIMIT = 3000  # max meters from city center

# Restaurant search
RESTAURANT_SEARCH_RADIUS = 2000  # meters from hotel
WALK_DISTANCE_MAX_METERS = 1500  # ~20 min walk
REVIEW_MINIMUM = 50  # minimum review count
REVIEW_MINIMUM_HIGH_RATING = 100  # for ratings >= 4.5

# Allowed cuisines (only these appear in brochures)
ALLOWED_CUISINES = [
    "Local", "Italian", "Croatian", "Grill", "Steakhouse", "Seafood"
]

# Cuisine filter keywords (any restaurant mentioning these is excluded)
EXCLUDED_CUISINE_KEYWORDS = [
    "turkish", "syrian", "asian", "halal", "chinese", "thai",
    "lebanese", "indian", "japanese", "korean", "vietnamese",
    "mexican", "african", "middle eastern", "indonesian",
    "filipino", "pakistani", "bangladeshi", "persian",
    "mediterranean"
]

# Charging station brands
PREFERRED_CHARGING_BRANDS = [
    "Circle K", "Fastned", "Ionity", "BP", "Shell",
    "EnBW Mobility", "E.ON Drive", "Allego"
]

CHARGING_STATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "data", "unique_locations.csv"
)

# PDF output
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "brochures")
WEEKEND_GUIDES_DIR = os.path.join(os.path.dirname(__file__), "..", "guides")

# Map screenshot dimensions for PDF inclusion
MAP_SCREENSHOT_WIDTH = 800
MAP_SCREENSHOT_HEIGHT = 600

# Charging stop recommendation
TARGET_ARRIVAL_BATTERY = 60.0  # target % when arriving at a charging stop or destination