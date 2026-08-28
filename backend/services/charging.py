"""EV route planning with charging station selection."""

import os
from datetime import datetime, timedelta

import folium
import geopandas as gpd
import pandas as pd
import shapely.geometry
from folium.plugins import BeautifyIcon

from . import geo
from .. import config


def _load_stations() -> gpd.GeoDataFrame | None:
    """Load charging stations from CSV and filter to preferred brands."""
    try:
        df = pd.read_csv(config.CHARGING_STATIONS_FILE, sep=";")
        df = df[df["Backend_Operator"].isin(config.PREFERRED_CHARGING_BRANDS)].copy()
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
            crs="EPSG:4326",
        )
        return gdf
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None


def _find_stations_along_route(
    route_coords: list, gdf: gpd.GeoDataFrame, buffer_m: int = 2000
) -> list[dict]:
    """Find charging stations within buffer of route line."""
    route_line = shapely.geometry.LineString(route_coords)
    buffered = route_line.buffer(buffer_m / 111000)  # approx degree conversion
    nearby = gdf[gdf.geometry.intersects(buffered)]
    results = []
    for _, s in nearby.iterrows():
        results.append({
            "brand": s.get("Backend_Operator", "N/A"),
            "latitude": s.geometry.y,
            "longitude": s.geometry.x,
            "location": f"{s.get('Address', '')}, {s.get('Zip_Code', '')} {s.get('City', '')}".strip(", "),
        })
    return results


def find_route_and_stations(
    start_address: str,
    end_address: str,
    start_battery: float,
) -> dict:
    """Calculate route, find stations, return map HTML + route info."""
    start_coords = geo.get_coordinates(start_address)
    end_coords = geo.get_coordinates(end_address)

    if not start_coords or not end_coords:
        return {"error": "Could not geocode addresses"}

    route, route_coords, distance, _ = geo.get_route_ors(start_coords, end_coords)
    if not route:
        return {"error": "Could not calculate route"}

    arrival = geo.remaining_battery(start_battery, distance)

    # Find charging stations
    stations = []
    gdf = _load_stations()
    if gdf is not None:
        stations = _find_stations_along_route(route_coords, gdf)

    # Build map
    m = folium.Map(location=start_coords, zoom_start=7)
    folium.GeoJson(
        route, name="Route",
        style_function=lambda x: {"color": "rgb(0,101,52)", "weight": 5},
    ).add_to(m)

    folium.Marker(
        start_coords,
        icon=BeautifyIcon(
            icon="home", prefix="fa", icon_shape="circle",
            border_color="purple", text_color="#009000", background_color="yellow",
        ),
        tooltip="Departure",
    ).add_to(m)
    folium.Marker(
        end_coords,
        icon=BeautifyIcon(
            icon="flag-checkered", prefix="fa", icon_shape="circle",
            border_color="purple", text_color="#000000", background_color="yellow",
        ),
        tooltip="Destination",
    ).add_to(m)

    for st in stations:
        folium.Marker(
            [st["latitude"], st["longitude"]],
            icon=BeautifyIcon(
                icon="charging-station", prefix="fa", icon_shape="circle",
                border_color="purple", text_color="#007799", background_color="yellow",
            ),
            tooltip=f"{st['brand']} - {st['location']}",
        ).add_to(m)

    return {
        "map_html": m._repr_html_(),
        "distance_km": round(distance, 2),
        "arrival_battery": round(arrival, 2),
        "start_coords": start_coords,
        "end_coords": end_coords,
        "stations": stations,
        "route_geojson": route,
        "route_coords": route_coords,
        "start_battery": start_battery,
    }


def plan_trip_with_stops(
    start_address: str,
    end_address: str,
    start_battery: float,
    selected_stations_out: list[dict],
    selected_stations_home: list[dict] | None = None,
) -> dict:
    """Plan multi-stop trip with charging stops.

    Returns markdown leg tables, charging station lists, map HTML, and trip summaries.
    """
    start_coords = geo.get_coordinates(start_address)
    end_coords = geo.get_coordinates(end_address)

    # --- WAY OUT ---
    result = _plan_leg(
        waypoints_raw=[(start_address, start_coords)]
                       + [(f"{s['brand']} - {s['location']}", (s["latitude"], s["longitude"])) for s in selected_stations_out]
                       + [(end_address, end_coords)],
        start_battery=start_battery,
        color_cycle=["blue", "green", "purple", "orange", "darkred"],
        direction="out",
    )

    # --- WAY HOME ---
    home_start = result["final_arrival_battery"]
    if selected_stations_home:
        home_result = _plan_leg(
            waypoints_raw=[(end_address, end_coords)]
                           + [(f"{s['brand']} - {s['location']}", (s["latitude"], s["longitude"])) for s in selected_stations_home]
                           + [(start_address, start_coords)],
            start_battery=home_start,
            color_cycle=["blue", "green", "purple", "orange", "darkred"],
            direction="home",
        )
    else:
        home_result = _plan_direct_route(end_coords, start_coords, home_start)

    return {
        "outbound": result,
        "return": home_result,
    }


def _plan_leg(waypoints_raw, start_battery, color_cycle, direction):
    """Plan a single direction with leg tables."""
    # Order stations by proximity
    ordered = []
    current = waypoints_raw[0][1]
    remaining = list(waypoints_raw[1:-1])  # stations only
    while remaining:
        next_stop = min(remaining, key=lambda s: geo.get_route_ors(current, s[1])[2] or float("inf"))
        ordered.append(next_stop)
        remaining.remove(next_stop)
        current = next_stop[1]

    waypoints = [waypoints_raw[0]] + ordered + [waypoints_raw[-1]]

    m = folium.Map(location=waypoints[0][1], zoom_start=7)
    battery = start_battery
    total_dist = 0
    total_drive = 0
    final_arrival = 0
    leg_rows = []
    charging_list = []

    for i in range(len(waypoints) - 1):
        start_name, start_c = waypoints[i]
        end_name, end_c = waypoints[i + 1]
        route, _, dist, _ = geo.get_route_ors(start_c, end_c)
        if not route:
            continue

        total_dist += dist
        total_drive += dist / config.AVERAGE_SPEED_KMPH
        arrival = geo.remaining_battery(battery, dist)

        short_s = start_name.split(" - ")[0].split(",")[0]
        short_e = end_name.split(" - ")[0].split(",")[0]
        leg_rows.append(f"| {i+1} | {short_s} \u2192 {short_e} | {dist:.1f} km | {arrival:.1f}% |")

        folium.GeoJson(
            route,
            name=f"Leg {i+1}",
            style_function=lambda x, c=color_cycle[i % len(color_cycle)]: {"color": c},
        ).add_to(m)

        icon_s = (
            BeautifyIcon(icon="home", prefix="fa", icon_shape="circle",
                         border_color="purple", text_color="#009000", background_color="yellow")
            if i == 0
            else BeautifyIcon(icon="charging-station", prefix="fa", icon_shape="circle",
                              border_color="purple", text_color="#007799", background_color="yellow")
        )
        folium.Marker(start_c, tooltip=f"{i}. {start_name}", icon=icon_s).add_to(m)

        if i < len(waypoints) - 2:
            battery = config.CHARGE_UP_TO_PERCENT
            charging_list.append(f"- **{ordered[i][0].split(' - ')[0]}** \u2014 {ordered[i][0].split(' - ', 1)[-1]}")
        else:
            final_arrival = arrival
            folium.Marker(
                end_c, tooltip=f"Destination: {end_name}",
                icon=BeautifyIcon(icon="flag-checkered", prefix="fa", icon_shape="circle",
                                  border_color="purple", text_color="#000000", background_color="yellow"),
            ).add_to(m)

    charge_hours = len(ordered) * (config.CHARGING_TIME_MINUTES / 60.0)
    total_hours = total_drive + charge_hours
    depart_time = datetime.now().replace(hour=17, minute=0) - timedelta(hours=total_hours)

    # Build markdown
    heading = ""
    table = "| Leg | From \u2192 To | Distance | Arrival Battery |\n"
    table += "|-----|-----------|----------|-----------------|\n"
    table += "\n".join(leg_rows)

    charging_md = ""
    if charging_list:
        charging_md = "\n\n**Charging stations used:**\n" + "\n".join(charging_list)

    summary = (
        f"\n\n**Trip summary:** {total_dist:.1f} km | "
        f"{geo.format_time_hm(total_hours)} "
        f"({geo.format_time_hm(total_drive)} driving + {geo.format_time_hm(charge_hours)} charging) | "
        f"Arrival battery: {final_arrival:.1f}%"
    )
    if direction == "out":
        summary += f" | Depart by: {depart_time.strftime('%I:%M %p')}"

    return {
        "markdown": heading + table + charging_md + summary,
        "map_html": m._repr_html_(),
        "final_arrival_battery": final_arrival,
        "total_distance": total_dist,
    }


def _plan_direct_route(end_coords, start_coords, start_battery):
    """Plan a direct return route with no stops."""
    m = folium.Map(location=end_coords, zoom_start=7)
    route, _, dist, _ = geo.get_route_ors(end_coords, start_coords)
    arrival = geo.remaining_battery(start_battery, dist)

    if route:
        folium.GeoJson(
            route, name="Return Route",
            style_function=lambda x: {"color": "red"},
        ).add_to(m)
    folium.Marker(
        end_coords, tooltip="Home Departure",
        icon=BeautifyIcon(icon="home", prefix="fa", icon_shape="circle",
                          border_color="purple", text_color="#009000", background_color="yellow"),
    ).add_to(m)
    folium.Marker(
        start_coords, tooltip="Final Arrival",
        icon=BeautifyIcon(icon="flag-checkered", prefix="fa", icon_shape="circle",
                          border_color="purple", text_color="#000000", background_color="yellow"),
    ).add_to(m)

    md = f"\n\nNo charging stops selected.\n- Direct route: {dist:.1f} km\n- Arrival battery: {arrival:.1f}%"

    return {
        "markdown": md,
        "map_html": m._repr_html_(),
        "final_arrival_battery": arrival,
        "total_distance": dist,
    }