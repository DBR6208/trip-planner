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


def _clean_restaurant_name(name: str | None) -> str:
    """Remove accidental list numbering returned by a place-search provider."""
    return re.sub(r"^\s*\d+[.)\-:]\s*", "", name or "").strip()


def _clean_restaurant_description(description: str | None) -> str:
    """Remove a copied leading list number from generated restaurant text."""
    return re.sub(r"^\s*\d+[.)\-:]\s*", "", description or "").strip()


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


def _excluded_cuisine_terms(*texts: str | None) -> set[str]:
    """Return excluded cuisine terms found in supplied restaurant evidence."""
    text = " ".join(part for part in texts if part).casefold()
    return {
        keyword
        for keyword in config.EXCLUDED_CUISINE_KEYWORDS
        if re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", text)
    }


def _is_cuisine_excluded(*texts: str | None) -> bool:
    """Check restaurant metadata or verified evidence for excluded cuisine terms."""
    return bool(_excluded_cuisine_terms(*texts))


def _get_cuisine_evidence(
    restaurant: dict,
    city: str | None,
    cache: dict[str, str],
) -> str:
    """Find independent web evidence about a candidate restaurant's cuisine.

    Google Places text search determines only the initial candidate set. This
    second step checks Tavily result titles and snippets before the candidate is
    presented as one of the app's allowed cuisine categories.
    """
    name = restaurant.get("name", "").strip()
    address = restaurant.get("address", "").strip()
    cache_key = f"{name.casefold()}|{address.casefold()}"
    if cache_key in cache:
        return cache[cache_key]
    if not name or not config.TAVILY_API_KEY:
        cache[cache_key] = ""
        return ""

    try:
        from tavily import TavilyClient

        location = address or city or ""
        response = TavilyClient(api_key=config.TAVILY_API_KEY).search(
            query=f'"{name}" "{location}" restaurant menu cuisine',
            search_depth="basic",
            max_results=3,
            include_answer=False,
        )
        chunks = []
        for result in response.get("results", []):
            title = result.get("title", "")
            content = result.get("content", "")
            if title or content:
                chunks.append(f"{title} {content}")
        evidence = "\n".join(chunks)
    except Exception as exc:
        print(f"Cuisine verification failed for '{name}': {exc}")
        evidence = ""

    cache[cache_key] = evidence
    return evidence


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
    cuisine_evidence_cache: dict[str, str] = {}

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
                "name": _clean_restaurant_name(p.get("name")),
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

            # First cuisine screen: reject obvious terms in the result name,
            # selected label, or restaurant website URL.
            if _is_cuisine_excluded(r["name"], cuisine, r.get("website")):
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

            # Second cuisine screen: verify search-query labels against
            # independent restaurant/menu web-search evidence. This catches,
            # for example, a Chinese seafood venue returned for "Seafood".
            cuisine_evidence = _get_cuisine_evidence(r, city, cuisine_evidence_cache)
            if _is_cuisine_excluded(cuisine_evidence):
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
        "prices or hours unless absolutely certain. Do not mention Asian, Chinese, Turkish, halal, "
        "fusion, or any other excluded cuisine/style. Max 25 words. Output only the sentence."
    )
    try:
        desc = llm.generate(prompt, max_tokens=80).strip().strip('"').strip()
        # The candidate should already have passed verified cuisine filtering.
        # Do not show a description that nonetheless introduces a blocked term.
        desc = _clean_restaurant_description(desc)
        return "" if _is_cuisine_excluded(desc) else desc[:200]
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
        # This output is also rendered in the Restaurants tab and supplied to
        # the itinerary generator, so it must not contain brochure-only page
        # break directives. The brochure builder adds those separately.
        sections.append(f"## {cuisine} Restaurants\n\n---")
        for r in rest_list:
            name = _clean_restaurant_name(r.get("name"))
            maps_url = geo.generate_maps_url(r.get("place_id", ""), "restaurant")
            desc = _clean_restaurant_description(r.get("description")) or _short_description(r)
            lines = [f"**{name}** ({cuisine})", ""]
            if desc:
                lines.append(desc)
                lines.append("")
            lines.append(f"- *Address:* {r.get('address', '')}")
            lines.append(
                f"- *Walk:* {r.get('walk_duration', 'N/A')} ({r.get('walk_distance', 'N/A')})"
            )
            lines.append(
                f"- *Rating:* {r.get('rating', 'N/A')} ({r.get('user_ratings_total', 0)} reviews)"
            )
            if r.get("website"):
                lines.append(f"- *Website:* [{name}]({r['website']})")
            if maps_url:
                lines.append(f"- *Google Maps:* [View on Map]({maps_url})")
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
    - Map centered on the average lat/lon of hotel + all restaurants.
    """
    if not hotel or not hotel.get("latitude"):
        return ""

    # Collect all valid lat/lng points for averaging
    hotel_lat = hotel["latitude"]
    hotel_lon = hotel["longitude"]
    points = [(hotel_lat, hotel_lon)]
    for r in restaurants:
        lat = r.get("latitude")
        lng = r.get("longitude")
        if lat is not None and lng is not None:
            points.append((lat, lng))

    avg_lat = sum(p[0] for p in points) / len(points)
    avg_lon = sum(p[1] for p in points) / len(points)
    center = (avg_lat, avg_lon)
    m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")

    # Hotel marker
    folium.Marker(
        location=(hotel_lat, hotel_lon),
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

        popup_links = []
        maps_url = geo.generate_maps_url(r.get("place_id", ""), "restaurant")
        if r.get("website"):
            popup_links.append(
                f'<a href="{r["website"]}" target="_blank" rel="noopener noreferrer">Website</a>'
            )
        if maps_url:
            popup_links.append(
                f'<a href="{maps_url}" target="_blank" rel="noopener noreferrer">Google Maps</a>'
            )
        popup_html = (
            f"<b>{r.get('name', 'Restaurant')}</b><br>"
            f"{cuisine} · {r.get('rating', 'N/A')}/5 "
            f"({r.get('user_ratings_total', 0)} reviews)<br>"
            f"Walk: {r.get('walk_duration', 'N/A')}"
        )
        if popup_links:
            popup_html += "<br>" + " | ".join(popup_links)

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