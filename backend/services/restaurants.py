"""Restaurant search with cuisine filtering, walking cap, review threshold."""

import re

import folium
from folium.plugins import BeautifyIcon

from . import geo, llm
from .. import config


# Cuisine color mapping for map markers
CUISINE_COLORS = {
    "Local": "#2E7D32",
    "Italian": "#C62828",
    "Croatian": "#1565C0",
    "Grill": "#E65100",
    "Steakhouse": "#6A1B9A",
    "Seafood": "#00838F",
}


def _cuisine_color(cuisine: str) -> str:
    """Get the map marker color for a cuisine type."""
    return CUISINE_COLORS.get(cuisine, "#757575")


def _get_place_details(place_id: str) -> dict:
    """Fetch website, phone, permanently_closed for a place."""
    if not place_id:
        return {}
    try:
        details = geo.gmaps().place(
            place_id=place_id,
            fields=["website", "formatted_phone_number", "permanently_closed"],
        )
        r = details.get("result", {})
        return {
            "website": r.get("website"),
            "phone_number": r.get("formatted_phone_number"),
            "permanently_closed": r.get("permanently_closed", False),
        }
    except Exception:
        return {}


def _is_cuisine_excluded(name: str, cuisine_label: str) -> bool:
    """Check if a restaurant name or cuisine type matches excluded keywords."""
    text = f"{name} {cuisine_label}".lower()
    for kw in config.EXCLUDED_CUISINE_KEYWORDS:
        if kw in text:
            return True
    return False


def find_restaurants(
    hotel_coords: tuple[float, float],
    cuisines: list[str],
    city: str | None = None,
) -> list[dict]:
    """Find restaurants near hotel filtered by allowed cuisines.

    Returns list of dicts with all filters applied:
    - Cuisine must be in the allowed set
    - Not permanently closed
    - Minimum review count
    - Within walking distance cap
    """
    all_restaurants = []
    seen_names = set()

    for cuisine in cuisines:
        query_parts = [cuisine, "restaurant"]
        if city:
            query_parts.append(f"in {city}")
        query = " ".join(query_parts)

        try:
            results = geo.gmaps().places(
                query=query,
                location=hotel_coords,
                radius=config.RESTAURANT_SEARCH_RADIUS,
                type="restaurant",
            )
        except Exception:
            continue

        places = []
        for p in results.get("results", [])[: config.MAX_RESULTS_TO_PROCESS]:
            loc = p.get("geometry", {}).get("location", {})
            places.append({
                "name": p.get("name"),
                "address": p.get("formatted_address", "N/A"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "place_id": p.get("place_id"),
                "rating": p.get("rating"),
                "user_ratings_total": p.get("user_ratings_total", 0),
                "cuisine": cuisine,
            })

        # Get walking distances
        places = geo.get_walking_distances(hotel_coords, places)

        # Get details (website, permanently_closed)
        for r in places:
            r.update(_get_place_details(r["place_id"]))

        # Apply filters
        for r in places:
            name_key = r["name"].lower().strip()
            if name_key in seen_names:
                continue

            # Filter: permanently closed
            if r.get("permanently_closed"):
                continue

            # Filter: cuisine exclusion keywords
            if _is_cuisine_excluded(r["name"], cuisine):
                continue

            # Filter: review count threshold
            reviews = r.get("user_ratings_total", 0) or 0
            if reviews < config.REVIEW_MINIMUM:
                continue

            # Filter: walking distance cap
            dist_m = geo.geodesic_distance(
                hotel_coords[0], hotel_coords[1],
                r["latitude"], r["longitude"],
            )
            if dist_m > config.WALK_DISTANCE_MAX_METERS:
                continue

            r["distance_meters"] = dist_m
            seen_names.add(name_key)
            all_restaurants.append(r)

    return all_restaurants


def _short_description(r: dict) -> str:
    """Generate a concise one-line description for a restaurant via the LLM."""
    name = r.get("name", "")
    cuisine = r.get("cuisine", "")
    rating = r.get("rating", "N/A")
    reviews = r.get("user_ratings_total", 0) or 0
    prompt = (
        f"Write ONE short, concrete sentence describing the {cuisine} restaurant '{name}' "
        f"(rating {rating}/5, {reviews} reviews). Describe the food, ambiance and what it is "
        "known for, in a practical travel tone. No lead-in, no closing remark, no emoji, no "
        "prices or hours unless absolutely certain. Max 25 words. Output only the sentence."
    )
    try:
        desc = llm.generate(prompt, max_tokens=80).strip().strip('"').strip()
        return desc[:200]
    except Exception:
        return ""


def format_restaurants(restaurants: list[dict]) -> str:
    """Format restaurants as compact markdown grouped by cuisine.

    No ### headings. Bold name only, then a short description and a plain
    bullet list of details.
    """
    if not restaurants:
        return "No restaurants found matching the selected criteria."

    # Group by cuisine
    by_cuisine: dict[str, list[dict]] = {}
    for r in restaurants:
        by_cuisine.setdefault(r["cuisine"], []).append(r)

    sections = []
    for cuisine, rest_list in by_cuisine.items():
        sections.append(f"## {cuisine} Restaurants\n\n---")
        for r in rest_list:
            maps_url = geo.generate_maps_url(r.get("place_id", ""), "restaurant")
            desc = r.get("description") or _short_description(r)
            lines = [f"**{r['name']}** ({cuisine})"]
            if desc:
                lines.append(desc)
                lines.append("")
            lines.append(f"- Address: {r.get('address', '')}")
            lines.append(
                f"- Walk: {r.get('walk_duration', 'N/A')} ({r.get('walk_distance', 'N/A')})"
            )
            lines.append(
                f"- Rating: {r.get('rating', 'N/A')} ({r.get('user_ratings_total', 0)} reviews)"
            )
            if r.get("website"):
                lines.append(f"- Website: [{r['name']}]({r['website']})")
            if maps_url:
                lines.append(f"- Google Maps: [View on Map]({maps_url})")
            lines.append("---")
            sections.append("\n".join(lines))

    return "\n\n".join(sections)


def generate_restaurant_map(
    hotel: dict | None,
    restaurants: list[dict],
) -> str:
    """Generate a Folium map with hotel marker + cuisine-colored restaurant markers.

    - Hotel: BeautifyIcon fa-hotel circle (same style as hotel map)
    - Restaurants: BeautifyIcon fa-utensils circle, colored by cuisine
    - Map centered on the hotel, zoom 15.
    """
    if not hotel or not hotel.get("latitude"):
        return ""

    center = (hotel["latitude"], hotel["longitude"])
    m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")

    # Hotel marker
    folium.Marker(
        location=center,
        tooltip=hotel.get("name", "Hotel"),
        icon=BeautifyIcon(
            icon="hotel",
            prefix="fa",
            icon_shape="circle",
            border_width=2,
            border_color="#8B0000",
            text_color="#FFFFFF",
            background_color="#8B0000",
            inner_icon_style="font-size: 12px;",
        ),
    ).add_to(m)

    # Restaurant markers
    for r in restaurants:
        lat = r.get("latitude")
        lng = r.get("longitude")
        if lat is None or lng is None:
            continue

        cuisine = r.get("cuisine", "")
        color = _cuisine_color(cuisine)
        popup_html = (
            f"<b>{r.get('name', 'Restaurant')}</b><br>"
            f"{cuisine} · {r.get('rating', 'N/A')}/5 "
            f"({r.get('user_ratings_total', 0)} reviews)<br>"
            f"Walk: {r.get('walk_duration', 'N/A')}"
        )

        folium.Marker(
            location=[lat, lng],
            tooltip=f"{r.get('name', '')} ({cuisine})",
            popup=folium.Popup(popup_html, max_width=300),
            icon=BeautifyIcon(
                icon="utensils",
                prefix="fa",
                icon_shape="circle",
                border_width=2,
                border_color=color,
                text_color="#FFFFFF",
                background_color=color,
                inner_icon_style="font-size: 12px;",
            ),
        ).add_to(m)

    return m._repr_html_()