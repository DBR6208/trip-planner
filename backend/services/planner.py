"""Weekend itinerary generation with actual user pattern."""

from . import llm
from .. import config


def generate_itinerary(
    city: str,
    hotel_name: str,
    hotel_address: str,
    restaurant_list: str,
    search_context: str,
) -> str:
    """Generate a weekend itinerary using the actual travel pattern.

    Rules:
    - No clock times, use time-of-day blocks
    - Restaurant refs: **Name** (cuisine, short tagline) only
    - No welcome/closing fluff
    - No emoji, no italic
    - Bold only for key items
    - Taxi fallback for walks >20 min or bad weather
    - Direct start on Friday, end after Sunday departure
    """
    prompt = f"""You are a concise travel planner. Create a day-by-day weekend plan for {city}.

The user is staying at **{hotel_name}** at {hotel_address}.

Use the search context below for inspiration about the city:
{search_context}

Important guidelines:
- Use time-of-day blocks (morning, afternoon, evening), not clock times.
- When referencing a restaurant, use only: **Name** (cuisine, short tagline) — no addresses, ratings, or websites here.
- If the walk to any restaurant or attraction exceeds 20 minutes, or if the weather is bad, suggest taking a taxi.
- The tone should be relaxed, practical, and concise.
- Bold only: restaurant names, hotel name, key numbers. No italic anywhere.
- Do NOT include any introductory welcome message, closing remarks, or "I hope you enjoy" text.
- Start directly with Friday. End immediately after Sunday departure.
- No emoji, no filler phrases.
- Budget guideline: ~1500-2000 EUR for 3 people (hotel, dinner, drinks — shopping and car not included).
- Recommend 4-5 star hotels only (3-star is not an option).

**User's weekend pattern (follow this structure exactly):**

## Friday Evening: Arrival
Arrive at the hotel around 5-6 PM, refresh, then:
- Start with a pre-dinner drink at the hotel bar to unwind and discuss the evening options.
- Take a short relaxed walk (up to ~20 minutes) to get a first impression of the city at night — a key landmark, lively square, or charming street.
- Walk to a restaurant for dinner. Reference restaurants from {restaurant_list} by **Name** (cuisine, short tagline) only — no addresses or ratings here.
- After dinner, return to the hotel for a nightcap and a game of UNO or cards before sleeping.
- If the walk to a restaurant exceeds 20 minutes or the weather is bad, suggest taking a taxi.

## Saturday: Exploration
- Start with breakfast at the hotel (mid-morning, around 9-11 AM).
- Suggest a relaxed walking tour of the city: mix of landmarks, local markets or flea markets, shopping streets or boutiques, and characteristic neighborhoods.
- Include a stop at the main tourist information office.
- Include a break for a light lunch, coffee and pastry at a local cafe.
- The afternoon should be relaxed — sightseeing, exploring, shopping.
- Return to the hotel in the late afternoon (around 5 PM).
- If the distance between attractions exceeds a 20-minute walk, suggest taking a taxi.

In the evening (after the return to the hotel):
- Start with a pre-dinner drink at the hotel bar.
- Take a short relaxed walk (different from the daytime route).
- Walk to a restaurant for dinner. Suggest a different restaurant from Friday.
- After dinner, return to the hotel for a nightcap and UNO or cards.
- If the walk exceeds 20 minutes or weather is bad, suggest a taxi.

## Sunday: Departure
- Start with breakfast at the hotel (mid-morning, around 9-11 AM).
- Pack luggage and check out (the hotel can store luggage if needed).
- Suggest a relaxing walk in the city — a promenade along a river, a park, a scenic neighborhood.
- Include a stop for a final drink at a typical local cafe or bar.
- Return to the hotel by early-to-mid afternoon to collect luggage.
- Depart so that arrival home is between 5-7 PM.

Ensure plans are cohesive — do not suggest the same major activity or restaurant twice.
The two evening plans must suggest different walks and different restaurants.
"""

    return llm.generate(
        prompt,
        system_prompt=(
            "You are a concise, practical travel planner. "
            "Output only the itinerary. No introductions, no conclusions, no emoji, no italic."
        ),
        max_tokens=3000,
    )