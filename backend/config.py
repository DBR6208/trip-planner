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
BATTERY_CAPACITY_KWH = 78.0
CONSUMPTION_KWH_PER_100KM = 17.31

# Hotel search
HOTEL_SEARCH_RADIUS = 1500  # meters from city center
HOTEL_DISTANCE_LIMIT = 3000  # max meters from city center

# Restaurant search (the selectable cuisines live in CUISINE_COLORS, restaurants.py)
WALK_DISTANCE_MAX_METERS = 2500  # max straight-line distance from hotel (~30 min walk); taxi is fine
REVIEW_MINIMUM = 50  # minimum review count

# Cuisine filter keywords (any restaurant mentioning these is excluded).
# Keep this list focused on cuisine/style terms rather than subjective labels.
EXCLUDED_CUISINE_KEYWORDS = [
    "turkish", "türkisch", "turkisch", "kebab", "kebap", "doner", "döner",
    "anatolian", "ottoman", "syrian", "asian", "fusion", "halal", "chinese", "thai",
    "lebanese", "indian", "japanese", "korean", "vietnamese",
    "greek", "griechisch", "griechische", "griechisches", "grec", "grecque",
    "grieks", "griekse", "gyros", "souvlaki",
    "turc", "turque", "turks", "turkse", "shoarma", "shawarma",
    "chinois", "chinees", "chinese", "japonais", "japans", "indien", "indiaas",
    "mexican", "african", "middle eastern", "indonesian",
    "filipino", "pakistani", "bangladeshi", "persian"
]

# Restaurant chains and franchises to leave out (matched on accent-free,
# lower-case words in the place name). Chains are also detected automatically
# when the same brand shows up more than once in the search results.
KNOWN_CHAINS = [
    "l'osteria", "vapiano", "block house", "maredo", "hans im glück",
    "peter pane", "alex", "nordsee", "ihop", "subway", "mcdonald's", "burger king",
    "kfc", "domino's", "pizza hut", "a&o", "dean & david", "jim block",
    "la vita e bella", "ristorante amalfi", "marché", "mövenpick", "hard rock",
    "brasserie flo", "léon", "buffalo grill", "hippopotamus", "courtepaille",
    "bistro romain", "del arte", "la boucherie", "pizza paï", "pizza pai",
    "exki", "le pain quotidien", "panos", "wagamama", "nando's",
    "pizza express", "zizzi", "prezzo", "bella italia", "ask italian",
    "loetje", "la place", "wok to walk",
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
WEEKEND_GUIDES_DIR = os.path.join(os.path.dirname(__file__), "..", "guides")
TEMP_GUIDES_DIR = os.path.join(WEEKEND_GUIDES_DIR, "temp")

# PDF renderer. Keep XeLaTeX as the default so the current production PDF
# workflow remains the immediate rollback path while Typst is evaluated.
PDF_ENGINE = os.getenv("PDF_ENGINE", "xelatex").strip().lower()
TYPST_COMMAND = os.getenv("TYPST_COMMAND", "typst")

# Map screenshot dimensions for PDF inclusion
MAP_SCREENSHOT_WIDTH = 800
MAP_SCREENSHOT_HEIGHT = 600

# Charging stop recommendation
TARGET_ARRIVAL_BATTERY = 60.0  # target % when arriving at a charging stop or destination