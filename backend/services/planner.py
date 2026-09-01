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
    prompt = f"""You are an experienced European travel writer. Create a relaxed, well-described weekend plan for {city}.

The user is staying at **{hotel_name}** at {hotel_address}.

Below is the city guide research (attractions, shopping streets, markets, culture — use this for detailed activity suggestions):
{search_context}

Below is the list of available restaurants with walk distances, ratings, and cuisine types. You MUST pick 2-3 specific restaurants for each of Friday evening and Saturday evening from this list. Use their actual names, walk distances, ratings, and cuisine:
RESTAURANT LIST:
{restaurant_list}

IMPORTANT GUIDELINES:
- Use time-of-day blocks (morning, afternoon, evening), not clock times. Example: "late afternoon" / "mid-evening" / "early afternoon" — not "5:00 PM" or "6:30 PM".
- For each evening, recommend 2-3 specific restaurants from the list above. For each, mention the **name**, the cuisine type, the walk time from the hotel, and the rating.
- If the walk to any restaurant or attraction exceeds 20 minutes, or if the weather is bad, suggest taking a taxi.
- The tone should be relaxed, practical, and richly descriptive — describe the atmosphere and character of the places visited.
- Bold only: restaurant names, hotel name, attraction names, and key numbers. No italic, no emoji, no filler phrases.
- Do NOT include any introductory welcome message, closing remarks, or "I hope you enjoy" text.
- Start directly with Friday. End immediately after Sunday departure.
- Do not use the same restaurant on both Friday and Saturday evenings.
- Budget guideline: ~1500-2000 EUR for 3 people (hotel, dinner, drinks — shopping and car not included).
- Recommend 4-5 star hotels only (3-star is not an option).

**User's weekend pattern (follow this structure — make it descriptive, not sparse):**

## Friday Evening: Arrival

Describe the arrival experience at the hotel around 5-6 PM in a relaxed tone. Refresh, then:
- Start with a pre-dinner drink at the hotel bar to unwind and discuss the evening options. Describe the atmosphere.
- Take a short relaxed walk (up to ~20 minutes) to get a first impression of the city at night — a key landmark, lively square, or charming street. Name the specific landmark or neighborhood. Mention the walking route.
- For dinner, list 2-3 specific restaurants from the RESTAURANT LIST above. For each, write a short description: name in bold, cuisine type, walk time from hotel, rating. Recommend one as the top choice and explain why (e.g. atmosphere, cuisine style, ratings).
- After dinner, return to the hotel for a nightcap and a game of UNO or cards before sleeping.
- If any walk exceeds 20 minutes or the weather is bad, suggest taking a taxi.

## Saturday: Exploration

Make this section rich and detailed with specific suggestions drawn from the city guide research:
- Start with breakfast at the hotel (mid-morning, around 9-11 AM).
- Suggest a relaxed walking tour of the city: name specific landmarks, squares, shopping streets or boutiques (from the city guide's shopping section), local markets or flea markets, and characteristic neighborhoods to explore. Be descriptive about what makes each stop interesting.
- Include a stop at the main tourist information office (mention it by name if known).
- Include a break for a light lunch, coffee and pastry at a local cafe — describe the kind of cafe and what to enjoy there.
- The afternoon should be relaxed — sightseeing, exploring, shopping. Name specific shopping streets, malls, or market areas from the city guide.
- Return to the hotel in the late afternoon (around 5 PM) to freshen up.
- If the distance between attractions exceeds a 20-minute walk, suggest taking a taxi.

In the evening (after returning to the hotel):
- Start with a pre-dinner drink at the hotel bar.
- Take a short relaxed walk — suggest a different route or neighborhood than the daytime walk.
- For dinner, list 2-3 specific restaurants from the RESTAURANT LIST (different from Friday's choices). For each, write a short description: name in bold, cuisine type, walk time from hotel, rating. Recommend one as the top choice.
- After dinner, return to the hotel for a nightcap and UNO or cards.
- If any walk exceeds 20 minutes or weather is bad, suggest a taxi.

## Sunday: Departure

- Start with breakfast at the hotel (mid-morning, around 9-11 AM).
- Pack luggage and check out (the hotel can store luggage if needed).
- Suggest a relaxing final walk in the city — a promenade along a river, a park, a scenic neighborhood. Name the specific location.
- Include a stop for a final drink at a typical local cafe or bar.
- Return to the hotel by early-to-mid afternoon to collect luggage.
- Depart so that arrival home is between 5-7 PM.

Ensure the plan feels cohesive and natural — do not suggest the same restaurant or major activity twice.
The two evening walks must be to different parts of the city.
"""

    return llm.generate(
        prompt,
        system_prompt=(
            "You are a descriptive, practical travel writer. "
            "Write in flowing, relaxed paragraphs and descriptive bullets — not sparse notes. "
            "Output only the itinerary. No introductions, no conclusions, no emoji, no italic."
        ),
        max_tokens=4000,
    )
