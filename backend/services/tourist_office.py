"""Tourist office lookup via Google Places."""

import folium

from . import geo
from .. import config


def _generate_google_maps_url(place_id: str) -> str | None:
    """Internal helper: Google Maps URL for a place_id."""
    if place_id:
        return (
            "https://www.google.com/maps/search/?api=1&query=tourist_office"
            f"&query_place_id={place_id}"
        )
    return None


def generate_tourist_office_map(city_name: str, office: dict) -> str:
    """Generate a Folium HTML map centered on the tourist office, with a marker.

    Returns the HTML string for embedding in the frontend.
    """
    if not office or not office.get("latitude") or not office.get("longitude"):
        # Fallback: centre on the city
        coords = geo.get_google_coords(city_name)
        if not coords:
            return ""
        lat, lng = coords
    else:
        lat, lng = office["latitude"], office["longitude"]

    m = folium.Map(location=[lat, lng], zoom_start=15, tiles="OpenStreetMap")

    if office and office.get("latitude") and office.get("longitude"):
        popup_html = f"<b>{office.get('name', 'Tourist Office')}</b><br>{office.get('address', '')}<br>"
        links = []
        if office.get("website"):
            links.append(
                f'<a href="{office["website"]}" target="_blank">Visit Website</a>'
            )
        maps_url = _generate_google_maps_url(office.get("place_id", ""))
        if maps_url:
            links.append(f'<a href="{maps_url}" target="_blank">View on Google Maps</a>')
        if links:
            popup_html += " | ".join(links)

        folium.Marker(
            location=[office["latitude"], office["longitude"]],
            tooltip=office.get("name", "Tourist Office"),
            popup=folium.Popup(popup_html, max_width=400),
            icon=folium.Icon(color="green", icon="info-sign", prefix="glyphicon"),
        ).add_to(m)

    return m._repr_html_()


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