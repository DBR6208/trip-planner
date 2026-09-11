"""Geocoding, routing, and distance services."""

import googlemaps
import openrouteservice
from geopy.geocoders import Nominatim
from geographiclib.geodesic import Geodesic

from .. import config

_gmaps = None
_ors = None
_geolocator = None


def gmaps() -> googlemaps.Client:
    global _gmaps
    if _gmaps is None:
        _gmaps = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)
    return _gmaps


def ors() -> openrouteservice.Client:
    global _ors
    if _ors is None:
        _ors = openrouteservice.Client(key=config.ORS_API_KEY)
    return _ors


def geolocator():
    global _geolocator
    if _geolocator is None:
        _geolocator = Nominatim(user_agent="my-trip-app")
    return _geolocator


def get_google_coords(address: str) -> tuple[float, float] | None:
    """Geocode an address using Google Maps API."""
    try:
        result = gmaps().geocode(address)
        if result:
            loc = result[0]["geometry"]["location"]
            return (loc["lat"], loc["lng"])
        return None
    except Exception:
        return None


def get_coordinates(address: str) -> tuple[float, float] | None:
    """Try Nominatim first, fall back to Google."""
    try:
        loc = geolocator().geocode(address)
        if loc:
            return (loc.latitude, loc.longitude)
        return get_google_coords(address)
    except Exception:
        return get_google_coords(address)


def get_city_from_coords(lat: float, lon: float) -> str | None:
    try:
        result = gmaps().reverse_geocode((lat, lon))
        if result:
            for comp in result[0]["address_components"]:
                if "locality" in comp["types"]:
                    return comp["long_name"]
        return None
    except Exception:
        return None


def geodesic_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance in meters between two points."""
    return Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)["s12"]


def get_route_ors(
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
):
    """Get route from ORS. Returns (route_geojson, geometry_coords, distance_km, duration_min)."""
    try:
        route = ors().directions(
            coordinates=[
                [start_coords[1], start_coords[0]],
                [end_coords[1], end_coords[0]],
            ],
            profile="driving-car",
            format="geojson",
        )
        geometry = route["features"][0]["geometry"]["coordinates"]
        distance = route["features"][0]["properties"]["segments"][0]["distance"] / 1000
        duration = route["features"][0]["properties"]["segments"][0]["duration"] / 60
        return route, geometry, distance, duration
    except Exception as e:
        print(f"ORS routing error: {e}")
        return None, None, None, None


def get_walking_distances(origin, destinations: list[dict]) -> list[dict]:
    """Add walking distance/duration from origin to each destination."""
    if not destinations:
        return destinations
    try:
        matrix = gmaps().distance_matrix(
            origins=[origin],
            destinations=[(d["latitude"], d["longitude"]) for d in destinations],
            mode="walking",
            units="metric",
        )
        if matrix["rows"]:
            for i, el in enumerate(matrix["rows"][0]["elements"]):
                if el["status"] == "OK":
                    destinations[i]["walk_distance"] = el["distance"]["text"]
                    destinations[i]["walk_duration"] = el["duration"]["text"]
                else:
                    destinations[i]["walk_distance"] = "N/A"
                    destinations[i]["walk_duration"] = "N/A"
        return destinations
    except Exception:
        return destinations


def generate_maps_url(place_id: str, place_type: str = "hotel") -> str | None:
    """Google Maps URL for a place_id. Uses direct place URL to avoid redirect warnings."""
    if place_id:
        return f"https://www.google.com/maps?q=place_id:{place_id}"
    return None


def remaining_battery(start_percent: float, distance_km: float) -> float:
    energy_used = (distance_km / 100) * config.CONSUMPTION_KWH_PER_100KM
    percent_used = (energy_used / config.BATTERY_CAPACITY_KWH) * 100
    return max(start_percent - percent_used, 0)


def battery_drop_for_distance(distance_km: float) -> float:
    """How much battery % is consumed over a given driving distance."""
    energy_used = (distance_km / 100) * config.CONSUMPTION_KWH_PER_100KM
    percent_used = (energy_used / config.BATTERY_CAPACITY_KWH) * 100
    return percent_used


def format_time_hm(hours: float) -> str:
    if hours < 0:
        return "0 minutes"
    h, m = divmod(int(hours * 60), 60)
    if h > 0 and m > 0:
        return f"{h} hours and {m} minutes"
    elif h > 0:
        return f"{h} hours"
    else:
        return f"{m} minutes"