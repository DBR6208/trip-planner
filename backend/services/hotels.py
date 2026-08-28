"""4-5 star hotel search near city center."""

from . import geo
from .. import config


def find_hotels(city_name: str) -> list[dict]:
    """Find 4 and 5-star hotels near city center.

    Returns list of dicts: name, address, lat, lng, place_id,
    star_rating, review_rating, website, reviews_total.
    """
    try:
        geocode = geo.gmaps().geocode(f"city center of {city_name}")
        if not geocode:
            return []
        center = geocode[0]["geometry"]["location"]
    except Exception:
        return []

    all_hotels = []
    seen_ids = set()

    for star in [5, 4]:
        query = f"{star} star hotels in {city_name}"
        try:
            result = geo.gmaps().places(
                query=query,
                location=center,
                radius=config.HOTEL_SEARCH_RADIUS,
                type="lodging",
            )
            for place in result.get("results", []):
                pid = place.get("place_id")
                if pid and pid not in seen_ids:
                    loc = place.get("geometry", {}).get("location", {})
                    if loc.get("lat") is not None:
                        dist = geo.geodesic_distance(
                            center["lat"], center["lng"], loc["lat"], loc["lng"]
                        )
                        if dist <= config.HOTEL_DISTANCE_LIMIT:
                            try:
                                det = geo.gmaps().place(
                                    pid, fields=["website", "formatted_address"]
                                )
                                d = det.get("result", {})
                            except Exception:
                                d = {}
                            all_hotels.append({
                                "name": place.get("name"),
                                "address": d.get("formatted_address", place.get("vicinity", "N/A")),
                                "latitude": loc["lat"],
                                "longitude": loc["lng"],
                                "place_id": pid,
                                "star_rating": f"{star}-star",
                                "review_rating": place.get("rating", "N/A"),
                                "website": d.get("website"),
                                "reviews_total": place.get("user_ratings_total", 0),
                            })
                            seen_ids.add(pid)
        except Exception:
            continue

    return all_hotels


def format_hotel(hotel: dict, description: str) -> str:
    """Format hotel as markdown with bold name + structured list + description.

    **Hotel Name**
    - *Address:* ...
    - *Website:* [name](url)
    - *Google Maps:* [View on Map](url)

    Description paragraph.
    """
    lines = [f"**{hotel.get('name', 'Hotel')}**\n"]
    lines.append(f"- *Address:* {hotel.get('address', '')}")
    if hotel.get("website"):
        lines.append(f"- *Website:* [{hotel['name']}]({hotel['website']})")
    maps_url = geo.generate_maps_url(hotel.get("place_id", ""))
    if maps_url:
        lines.append(f"- *Google Maps:* [View on Map]({maps_url})")
    lines.append(f"\n{description}")
    return "\n".join(lines)