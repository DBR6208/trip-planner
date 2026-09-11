"""4-5 star hotel search near city center."""

import folium
from folium.plugins import BeautifyIcon

from . import geo
from .. import config


def _tavily_search_hotel(hotel_name: str, city: str) -> str:
    """Search the web for content about a specific hotel.

    Returns concatenated search snippets as plain text.
    """
    try:
        from tavily import TavilyClient

        tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
        query = f"{hotel_name} {city} hotel review cleanliness bar lounge restaurant parking amenities"
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )
        chunks = []
        if response.get("answer"):
            from ..services.city_guide import clean_text
            chunks.append(clean_text(response["answer"]))
        for r in response.get("results", []):
            content = r.get("content", "")
            if content:
                chunks.append(f"SOURCE ({r.get('title', '')}): {content[:1500]}")
        return "\n\n".join(chunks) if chunks else ""
    except Exception as e:
        print(f"Tavily hotel search error: {e}")
        return ""


def _find_nearby_parking(hotel_name: str, lat: float, lng: float) -> list[dict]:
    """Find indoor parking garages near a hotel via Google Places.

    Returns up to 5 closest garages sorted by distance.
    """
    parkings = []
    seen_ids = set()
    try:
        result = geo.gmaps().places(
            query=f"parking garage near {hotel_name}",
            location={"lat": lat, "lng": lng},
            radius=500,  # 500m radius around hotel
            type="parking",
        )
        for place in result.get("results", []):
            pid = place.get("place_id")
            if pid and pid not in seen_ids:
                loc = place.get("geometry", {}).get("location", {})
                if loc.get("lat") is not None:
                    try:
                        det = geo.gmaps().place(
                            pid, fields=["formatted_address"]
                        )
                        addr = det.get("result", {}).get(
                            "formatted_address", place.get("vicinity", "")
                        )
                    except Exception:
                        addr = place.get("vicinity", "")
                    parkings.append({
                        "name": place.get("name", ""),
                        "address": addr,
                        "place_id": pid,
                        "latitude": loc["lat"],
                        "longitude": loc["lng"],
                        "distance_m": geo.geodesic_distance(
                            lat, lng, loc["lat"], loc["lng"]
                        ),
                    })
                    seen_ids.add(pid)
    except Exception as e:
        print(f"Parking search error: {e}")

    # Sort by distance and keep 5 closest
    parkings.sort(key=lambda p: p.get("distance_m", 9999))
    return parkings[:5]


def _enrich_hotel(place: dict, center: dict, star_rating: str) -> dict | None:
    """Build a hotel dict from a Google Places result, or None if out of range."""
    pid = place.get("place_id")
    loc = place.get("geometry", {}).get("location", {})
    if not pid or loc.get("lat") is None:
        return None
    dist = geo.geodesic_distance(
        center["lat"], center["lng"], loc["lat"], loc["lng"]
    )
    if dist > config.HOTEL_DISTANCE_LIMIT:
        return None
    try:
        det = geo.gmaps().place(
            pid, fields=["website", "formatted_address", "photo"]
        )
        d = det.get("result", {})
    except Exception:
        d = {}
    photo_url = ""
    if d.get("photos"):
        ref = d["photos"][0].get("photo_reference", "")
        if ref:
            photo_url = (
                "https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth=800&photoreference={ref}"
                f"&key={config.GOOGLE_MAPS_API_KEY}"
            )
    return {
        "name": place.get("name"),
        "address": d.get("formatted_address", place.get("vicinity", "N/A")),
        "latitude": loc["lat"],
        "longitude": loc["lng"],
        "place_id": pid,
        "star_rating": star_rating,
        "review_rating": place.get("rating", "N/A"),
        "website": d.get("website"),
        "reviews_total": place.get("user_ratings_total", 0),
        "photo_url": photo_url,
    }


def find_hotels(city_name: str) -> list[dict]:
    """Find 4 and 5-star hotels near city center.

    Uses two strategies in combination:
      1. Nearby search (type=lodging) — finds ALL lodging in the area, then
         uses price_level / rating to classify 4-5 star equivalent.
      2. Text search fallback — for hotels Google explicitly indexes as
         "4 star hotels in X" / "5 star hotels in X".

    Both use pagination (up to 3 pages each) to avoid the 20-result-per-page cap
    that was the root cause of missing hotels like Hotel Remarque in Osnabrück.
    Results are deduplicated by place_id.

    Returns list of dicts: name, address, lat, lng, place_id,
    star_rating, review_rating, website, reviews_total, photo_url.
    """
    import time

    try:
        geocode = geo.gmaps().geocode(f"city center of {city_name}")
        if not geocode:
            return []
        center = geocode[0]["geometry"]["location"]
    except Exception:
        return []

    all_hotels = []
    seen_ids = set()

    # ── Step 1: nearby search (comprehensive, catches every lodging) ──
    for page in range(3):
        try:
            params: dict = {
                "location": center,
                "radius": config.HOTEL_SEARCH_RADIUS,
                "type": "lodging",
            }
            if page > 0:
                params["page_token"] = page_token  # type: ignore[name-defined]
            result = geo.gmaps().places_nearby(**params)

            for place in result.get("results", []):
                pid = place.get("place_id")
                if pid and pid in seen_ids:
                    continue

                # Classify quality via price_level + rating heuristics
                pl = place.get("price_level")
                ratings_score = place.get("rating", 0) or 0
                reviews = place.get("user_ratings_total", 0) or 0

                if pl is not None and pl >= 4:
                    star = "5-star"
                elif pl is not None and pl >= 3:
                    star = "4-star"
                elif ratings_score >= 4.5 and reviews >= 50:
                    star = "5-star"
                elif ratings_score >= 4.0 and reviews >= 100:
                    star = "4-star"
                else:
                    continue  # not high-enough quality

                hotel = _enrich_hotel(place, center, star)
                if hotel:
                    all_hotels.append(hotel)
                    seen_ids.add(pid)

            page_token = result.get("next_page_token")
            if not page_token:
                break
            time.sleep(2)  # Google requires ~2s delay before using page_token
        except Exception:
            break

    # ── Step 2: text-search fallback (catches explicitly classified hotels) ──
    for star_text in ["5", "4"]:
        query = f"{star_text} star hotels in {city_name}"
        text_result = None
        text_page_token = None
        for _ in range(3):
            try:
                params: dict = {
                    "query": query,
                    "location": center,
                    "radius": config.HOTEL_SEARCH_RADIUS,
                    "type": "lodging",
                }
                if text_page_token:
                    params["page_token"] = text_page_token
                text_result = geo.gmaps().places(**params)

                for place in text_result.get("results", []):
                    pid = place.get("place_id")
                    if pid and pid in seen_ids:
                        continue
                    hotel = _enrich_hotel(place, center, f"{star_text}-star")
                    if hotel:
                        all_hotels.append(hotel)
                        seen_ids.add(pid)

                text_page_token = text_result.get("next_page_token")
                if not text_page_token:
                    break
                time.sleep(2)
            except Exception:
                break

    return all_hotels


def format_hotel(hotel: dict, description: str, parkings: list[dict] | None = None) -> str:
    """Format hotel as markdown with bold name + structured list + description + parking.

    **Hotel Name**

    - *Address:* ...
    - *Website:* [name](url)
    - *Google Maps:* [View on Map](url)

    Description paragraph.

    Nearby indoor parking garages:
    - **Garage Name** — Address — [View on Map](url)
    ...
    """
    lines = [f"**{hotel.get('name', 'Hotel')}**\n"]
    lines.append(f"- *Address:* {hotel.get('address', '')}")
    if hotel.get("website"):
        lines.append(f"- *Website:* [{hotel['name']}]({hotel['website']})")
    maps_url = geo.generate_maps_url(hotel.get("place_id", ""))
    if maps_url:
        lines.append(f"- *Google Maps:* [View on Map]({maps_url})")
    lines.append(f"\n{description}")

    # Parking — proper bullet list with blank line before list
    if parkings:
        lines.append("\n**Nearby indoor parking garages:**  \n")
        for p in parkings:
            pmaps = geo.generate_maps_url(p.get("place_id", ""), "parking")
            name = p.get("name", "")
            addr = p.get("address", "")
            if pmaps:
                lines.append(
                    f"- **{name}** — {addr} — "
                    f"[Google Maps]({pmaps})"
                )
            else:
                lines.append(f"- **{name}** — {addr}")
    else:
        lines.append(
            "\n*No nearby indoor parking garages within walking distance.*"
        )

    return "\n".join(lines)


def _gmaps_url(place_id: str) -> str | None:
    """Google Maps URL for a place_id. Direct place URL avoids redirect warnings."""
    if place_id:
        return f"https://www.google.com/maps?q=place_id:{place_id}"
    return None


def generate_hotel_map(
    hotels: list[dict],
    tourist_office: dict | None = None,
    selected_hotel_id: str | None = None,
    parkings: list[dict] | None = None,
) -> str:
    """Generate a Folium map showing tourist office + hotel + parking markers.

    - 5-star selected: darkred circle BeautifyIcon with fa-hotel
    - 4-star selected: orange circle BeautifyIcon with fa-hotel
    - Unselected hotels: very light grey
    - When no selection yet (selected_hotel_id is None): all hotels in color
    - Parking garages (shown only when a hotel is selected): blue circle BeautifyIcon with fa-parking
    - Tourist office: green 'info-sign' icon
    - Map centred on the tourist office (or first hotel), zoom 15.
    """
    # Determine centre
    center = None
    if tourist_office and tourist_office.get("latitude"):
        center = (tourist_office["latitude"], tourist_office["longitude"])
    if not center and hotels:
        center = (hotels[0]["latitude"], hotels[0]["longitude"])
    if not center:
        return ""

    m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")

    # Tourist office marker (always prominent)
    if tourist_office and tourist_office.get("latitude"):
        to_popup = f"<b>{tourist_office.get('name', 'Tourist Office')}</b><br>{tourist_office.get('address', '')}<br>"
        to_links = []
        if tourist_office.get("website"):
            to_links.append(
                f'<a href="{tourist_office["website"]}" target="_blank" rel="noopener noreferrer">Website</a>'
            )
        to_maps = _gmaps_url(tourist_office.get("place_id", ""))
        if to_maps:
            to_links.append(f'<a href="{to_maps}" target="_blank" rel="noopener noreferrer">Google Maps</a>')
        if to_links:
            to_popup += " | ".join(to_links)
        folium.Marker(
            location=[tourist_office["latitude"], tourist_office["longitude"]],
            tooltip=tourist_office.get("name", "Tourist Office"),
            popup=folium.Popup(to_popup, max_width=400),
            icon=folium.Icon(color="green", icon="info-sign", prefix="glyphicon"),
        ).add_to(m)

    # Hotel markers — BeautifyIcon with hotel icon, larger
    has_selection = selected_hotel_id is not None
    for h in hotels:
        is_selected = has_selection and h.get("place_id") == selected_hotel_id

        if not has_selection:
            # All in color
            icon_color = "#8B0000" if "5" in h.get("star_rating", "") else "#FF8C00"
        elif is_selected:
            icon_color = "#8B0000" if "5" in h.get("star_rating", "") else "#FF8C00"
        else:
            icon_color = "#b0b0b0"  # medium-light grey

        popup_html = f"<b>{h.get('name', 'Hotel')}</b><br>"
        links = []
        if h.get("website"):
            links.append(
                f'<a href="{h["website"]}" target="_blank" rel="noopener noreferrer">Website</a>'
            )
        hmaps = _gmaps_url(h.get("place_id", ""))
        if hmaps:
            links.append(f'<a href="{hmaps}" target="_blank" rel="noopener noreferrer">Google Maps</a>')
        if links:
            popup_html += " | ".join(links)
        popup_html += f'<br><small>{h.get("star_rating", "")} · {h.get("review_rating", "")} ({h.get("reviews_total", 0)})</small>'

        folium.Marker(
            location=[h["latitude"], h["longitude"]],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=h.get("name", ""),
            icon=BeautifyIcon(
                icon="hotel",
                prefix="fa",
                icon_shape="circle",
                border_width=2,
                border_color=icon_color,
                text_color="#FFFFFF",
                background_color=icon_color,
                inner_icon_style="font-size: 12px;",
            ),
        ).add_to(m)

    # Parking markers — blue circle with fa-parking, shown only when a hotel is selected
    if parkings and selected_hotel_id:
        for p in parkings:
            if p.get("latitude") and p.get("longitude"):
                folium.Marker(
                    location=[p["latitude"], p["longitude"]],
                    tooltip=p.get("name", "Parking"),
                    popup=folium.Popup(
                        f"<b>{p.get('name', 'Parking')}</b><br>{p.get('address', '')}",
                        max_width=300,
                    ),
                    icon=BeautifyIcon(
                        icon="parking",
                        prefix="fa",
                        icon_shape="circle",
                        border_width=2,
                        border_color="#1565C0",
                        text_color="#FFFFFF",
                        background_color="#1565C0",
                        inner_icon_style="font-size: 12px;",
                    ),
                ).add_to(m)

    return m._repr_html_()