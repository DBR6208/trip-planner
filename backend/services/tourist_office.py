"""Tourist office lookup via Google Places."""

from . import geo
from .. import config


def find_tourist_office(city_name: str) -> dict | None:
    """Find tourist information office in a city.

    Returns dict with name, address, place_id, lat, lng, website,
    or None if not found.
    """
    try:
        result = geo.gmaps().places(
            query=f"tourist information office in {city_name}"
        )
        if not result or not result.get("results"):
            return None

        office = result["results"][0]
        place_id = office.get("place_id")
        details = geo.gmaps().place(
            place_id=place_id, fields=["website", "formatted_address"]
        )
        d_result = details.get("result", {})

        return {
            "name": office.get("name"),
            "address": d_result.get(
                "formatted_address", office.get("formatted_address", "")
            ),
            "place_id": place_id,
            "latitude": office["geometry"]["location"]["lat"],
            "longitude": office["geometry"]["location"]["lng"],
            "website": d_result.get("website"),
        }
    except Exception as e:
        print(f"Tourist office lookup error: {e}")
        return None


def format_tourist_office(office: dict) -> str:
    """Format tourist office as a structured markdown list.

    - *Address:* ...
    - *Website:* [name](url)
    - *Google Maps:* [View on Map](url)
    """
    if not office:
        return "Tourist office information not available."

    maps_url = geo.generate_maps_url(office.get("place_id", ""), "tourist_office")
    lines = [f"- *Address:* {office.get('address', '')}"]
    if office.get("website"):
        lines.append(f"- *Website:* [{office['name']}]({office['website']})")
    if maps_url:
        lines.append(f"- *Google Maps:* [View on Map]({maps_url})")
    return "\n".join(lines)