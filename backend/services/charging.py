"""EV route planning with charging station selection."""

import os
from datetime import datetime, timedelta

import folium
import ftfy
import geopandas as gpd
import pandas as pd
import shapely.geometry
from folium.plugins import BeautifyIcon

from . import geo
from .. import config


def _recommend_stations_greedy(
    route_coords: list,
    stations: list[dict],
    start_battery: float,
    total_distance_km: float,
    reverse: bool = False,
) -> list[dict]:
    """Recommend minimal charging stops to arrive with ~target battery.

    Strategy: if the current battery can't reach the end with at least the target
    battery (60%), find a station that:
      a) is reachable (arrival >= min_battery 20%)
      b) after charging to 90%, we can reach the next checkpoint or end with min 20%
    Among those, pick the best brand (Circle K > Ionity > Fastned > others).
    Repeat from that station until the end is reachable. Minimizes stops by
    only charging when needed.

    Brand preference: Circle K → Ionity → Fastned → others.

    Args:
        route_coords: list of (lat, lon) tuples
        stations: list of station dicts
        start_battery: starting battery %
        total_distance_km: actual route distance in km (from OSRM, not calculated from coords)
        reverse: if True, plan return trip (reverse direction)

    Returns list of recommended station dicts (empty if none needed).
    """
    charge_to = config.CHARGE_UP_TO_PERCENT
    target = config.TARGET_ARRIVAL_BATTERY
    min_battery = 15.0  # Minimum at any charging stop (15% = safe margin)

    BRAND_PRIORITY = {
        "Circle K": 0,
        "Ionity": 1,
        "Fastned": 2,
    }

    if not route_coords or not stations:
        return []

    line = shapely.geometry.LineString(route_coords)
    
    # Project stations onto route using simple line projection
    # (total_distance_km from OSRM is more accurate than reconstructing from coords)
    projected = []
    for s in stations:
        pt = shapely.geometry.Point(s["longitude"], s["latitude"])
        # Project onto the route line (normalized 0-1, then scale by total distance)
        proj_norm = line.project(pt, normalized=True)
        s_dist = proj_norm * total_distance_km
        
        priority = BRAND_PRIORITY.get(s.get("brand", ""), 99)
        projected.append({**s, "_dist": s_dist, "_prio": priority})

    total_length = total_distance_km

    if reverse:
        projected.sort(key=lambda x: total_length - x["_dist"])
        current_pos = total_length
        end_pos = 0
    else:
        projected.sort(key=lambda x: x["_dist"])
        current_pos = 0
        end_pos = total_length

    recommended = []
    battery = start_battery
    max_iterations = 10  # Safety limit
    used_stations = set()  # Track stations we've already charged at
    
    # Special case: if starting battery is too low to reach ANY station on route,
    # must charge at the nearest station FIRST
    if reverse:
        # For reverse (returning), find closest station to current start position
        min_dist_to_station = min(abs(s["_dist"] - current_pos) for s in projected) if projected else float('inf')
    else:
        # For outbound, same logic
        min_dist_to_station = min(abs(s["_dist"] - current_pos) for s in projected) if projected else float('inf')
    
    if min_dist_to_station < float('inf'):
        battery_to_nearest = geo.remaining_battery(battery, min_dist_to_station)
        if battery_to_nearest < min_battery:
            # Must charge immediately - find closest station and add it
            closest_station = min(projected, key=lambda s: abs(s["_dist"] - current_pos))
            recommended.append({k: v for k, v in closest_station.items() if not k.startswith("_")})
            used_stations.add((closest_station["location"], closest_station["brand"]))
            battery = charge_to
            current_pos = closest_station["_dist"]

    for iteration in range(max_iterations):
        # Can we reach the end with at least the target battery?
        remaining_to_end = abs(end_pos - current_pos)
        if geo.remaining_battery(battery, remaining_to_end) >= target:
            break  # no charge needed

        # Need a charge. Find viable candidates (excluding already-used stations).
        candidates = []
        for s in projected:
            s_dist = s["_dist"]
            s_leg = abs(s_dist - current_pos)
            
            # Skip if too close or already used
            if s_leg < 1:
                continue
            s_key = (s["location"], s["brand"])
            if s_key in used_stations:
                continue
            
            s_arrival = geo.remaining_battery(battery, s_leg)
            
            # Special case for initial leg of return journey: if battery is critically low,
            # accept any station we can physically reach, even if below min_battery
            if iteration == 0 and reverse and battery < 70.0:
                if s_arrival < 0:  # Can't reach even this far
                    continue
                # Don't check final_arrival for this first stop, just recommend it
                candidates.append(s)
            else:
                # Normal case: require safe margins
                if s_arrival < min_battery:
                    continue
                # After charging, check if we can reach destination reasonably
                remaining_after = abs(end_pos - s_dist)
                final_arrival = geo.remaining_battery(charge_to, remaining_after)
                min_acceptable = config.TARGET_ARRIVAL_BATTERY - 5.0
                if final_arrival >= min_acceptable:
                    candidates.append(s)

        if not candidates:
            break

        # Best candidate: farthest reachable (to minimize stops).
        # Among equal distance, prefer better brand.
        candidates.sort(key=lambda x: (
            -abs(x["_dist"] - current_pos),  # farthest first (minimize stops)
            x["_prio"],  # then best brand
        ))
        chosen = candidates[0]

        recommended.append({k: v for k, v in chosen.items() if not k.startswith("_")})
        used_stations.add((chosen["location"], chosen["brand"]))
        battery = charge_to
        current_pos = chosen["_dist"]

    return recommended


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
    route_coords: list, gdf: gpd.GeoDataFrame, buffer_m: int = 5000
) -> list[dict]:
    """Find charging stations within buffer of route line (5km default)."""
    route_line = shapely.geometry.LineString(route_coords)
    buffered = route_line.buffer(buffer_m / 111000)  # approx degree conversion
    nearby = gdf[gdf.geometry.intersects(buffered)]
    results = []
    for _, s in nearby.iterrows():
        results.append({
            "brand": s.get("Backend_Operator", "N/A"),
            "latitude": s.geometry.y,
            "longitude": s.geometry.x,
            "location": ftfy.fix_text(
                f"{s.get('Address', '')}, {s.get('Zip_Code', '')} {s.get('City', '')}".strip(", ")
            ),
        })
    return results


# ── NEW: BFS-based optimal charging route search ──


def _build_battery_matrix(
    stations: list[dict],
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
) -> tuple[pd.DataFrame, dict[str, dict]] | None:
    """
    Build a battery drop % matrix using ORS distance matrix (actual road distances).

    Returns (DataFrame indexed by labels, label->station lookup dict) or None on failure.
    """
    locations = []
    labels = []
    station_map: dict[str, dict] = {}

    # START
    locations.append([start_coords[1], start_coords[0]])  # ORS wants [lon, lat]
    labels.append("START")

    # Stations
    for i, s in enumerate(stations):
        locations.append([s["longitude"], s["latitude"]])
        label = f"{i}:{s['brand']}|{s['location']}"
        labels.append(label)
        station_map[label] = s

    # DESTINATION
    locations.append([end_coords[1], end_coords[0]])
    labels.append("DESTINATION")

    try:
        n = len(locations)
        result = geo.ors().distance_matrix(
            locations=locations,
            profile="driving-car",
            sources=list(range(n)),
            destinations=list(range(n)),
            metrics=["distance"],
            units="m",
            validate=True,
        )
        df = pd.DataFrame(result["distances"], index=labels, columns=labels)
        # Convert meters -> km -> battery drop %
        df_km = df / 1000
        df_drop = df_km.map(geo.battery_drop_for_distance)
        return df_drop, station_map
    except Exception as e:
        print(f"ORS distance matrix failed: {e}")
        return None


def _bfs_search_route(
    battery_matrix: pd.DataFrame,
    route_geometry: list,
    station_map: dict[str, dict],
    reverse: bool = False,
) -> list[dict] | None:
    """
    Find optimal charging route via BFS over the battery-drop graph.

    Strategy:
      1. Start at START, explore depth-by-depth (fewest stops first).
      2. Intermediate hops must consume 30-60% battery.
      3. Final hop to DESTINATION must consume 30-35%.
      4. Every stop must be forward along the route.
      5. No station visited twice.
      6. Among equal-length paths, pick lowest penalty
         (battery deviation + brand preference).

    If no path found, constraints are relaxed gradually and search retries:
      - Intermediate bounds widen by ±5/10% per attempt
      - Destination bounds widen by ±5% per attempt
      Up to 4 attempts, then returns None.

    Returns list of recommended station dicts (same format as greedy fallback).
    """
    BRAND_PRIORITY = {"Circle K": 0, "Ionity": 1, "Fastned": 2}

    start_label = "START"
    destination_label = "DESTINATION"

    route_line = shapely.geometry.LineString(route_geometry)
    route_length = route_line.length

    # --- helper functions ---

    def get_value(a: str, b: str) -> float | None:
        val = battery_matrix.loc[a, b]
        return float(val) if not pd.isna(val) else None

    def station_point(label: str):
        if label in (start_label, destination_label):
            return None
        s = station_map.get(label)
        return shapely.geometry.Point(s["longitude"], s["latitude"]) if s else None

    # Precompute route positions (0 = home, route_length = destination)
    route_positions: dict[str, float] = {
        start_label: 0.0,
        destination_label: route_length,
    }
    for label in battery_matrix.index:
        if label in (start_label, destination_label):
            continue
        pt = station_point(label)
        if pt:
            route_positions[label] = route_line.project(pt)

    def forward_check(pos_a: float, pos_b: float) -> bool:
        """Is posB ahead of posA toward the destination?"""
        return pos_b <= pos_a if reverse else pos_b >= pos_a

    def brand_penalty(label: str) -> int:
        if ":" not in label:
            return 0
        brand = label.split(":")[1].split("|")[0].strip()
        return BRAND_PRIORITY.get(brand, 99)

    def calc_penalty(path: list[str], d_min: float, d_max: float, i_min: float, i_max: float) -> float:
        penalty = 0.0
        for a, b in zip(path[:-1], path[1:]):
            drop = get_value(a, b)
            if drop is None:
                return float("inf")
            target = (d_min + d_max) / 2.0 if b == destination_label else (i_min + i_max) / 2.0
            penalty += abs(drop - target) * 10  # battery deviation
            if b != destination_label:
                penalty += brand_penalty(b)
        return penalty

    def bfs_at_bounds(d_min: float, d_max: float, i_min: float, i_max: float, max_hops: int = 20):
        """Run BFS with given battery bounds. Returns best path labels or None."""
        frontier: list[tuple[list[str], set[str]]] = [([start_label], {start_label})]

        for _depth in range(max_hops + 1):
            completed: list[list[str]] = []
            next_frontier: list[tuple[list[str], set[str]]] = []

            for path, used in frontier:
                current = path[-1]
                c_to_dest = get_value(current, destination_label)
                if c_to_dest is None:
                    continue
                cur_pos = route_positions.get(current)
                if cur_pos is None:
                    continue

                # Directly reachable destination?
                if d_min <= c_to_dest <= d_max:
                    completed.append(path + [destination_label])
                    continue

                for candidate in route_positions:
                    if candidate in used or candidate == current:
                        continue
                    if candidate in (start_label, destination_label):
                        continue

                    hop = get_value(current, candidate)
                    if hop is None:
                        continue
                    cand_to_dest = get_value(candidate, destination_label)
                    if cand_to_dest is None:
                        continue
                    cand_pos = route_positions.get(candidate)
                    if cand_pos is None:
                        continue
                    if not forward_check(cur_pos, cand_pos):
                        continue
                    if i_min <= hop <= i_max:
                        next_frontier.append((path + [candidate], used | {candidate}))

            if completed:
                return min(completed, key=lambda p: calc_penalty(p, d_min, d_max, i_min, i_max))

            # Deduplicate frontier
            dedup: dict[tuple, tuple[list[str], set[str]]] = {}
            for p, u in next_frontier:
                k = tuple(p)
                if k not in dedup:
                    dedup[k] = (p, u)
            frontier = list(dedup.values())

        return None

    # --- graduated constraint relaxation ---
    for attempt in range(4):
        dest_min = max(10, 30 - attempt * 5)
        dest_max = min(70, 35 + attempt * 5)
        inter_min = max(10, 30 - attempt * 5)
        inter_max = min(85, 60 + attempt * 10)

        result_path = bfs_at_bounds(dest_min, dest_max, inter_min, inter_max)
        if result_path is not None:
            # Map labels back to station dicts
            stations_out = []
            for label in result_path:
                if label in (start_label, destination_label):
                    continue
                s = station_map.get(label)
                if s:
                    stations_out.append(dict(s))
            return stations_out

    return None


# ── Primary station recommendation: BFS first, greedy fallback ──


def _recommend_stations(
    route_coords: list,
    stations: list[dict],
    start_battery: float,
    total_distance_km: float,
    reverse: bool = False,
) -> list[dict]:
    """
    Recommend optimal charging stops.
    Uses BFS + ORS distance matrix. Falls back to greedy if BFS fails.
    """
    if not route_coords or not stations:
        return []

    # BFS path: needs start/end coords for the distance matrix
    start_coords = (route_coords[0][1], route_coords[0][0])  # geo uses (lat, lon)
    end_coords = (route_coords[-1][1], route_coords[-1][0])

    try:
        matrix_data = _build_battery_matrix(stations, start_coords, end_coords)
        if matrix_data is not None:
            battery_matrix, station_map = matrix_data
            bfs_result = _bfs_search_route(
                battery_matrix, route_coords, station_map, reverse=reverse,
            )
            if bfs_result is not None:
                return bfs_result
    except Exception as e:
        print(f"BFS recommendation failed, falling back to greedy: {e}")

    return _recommend_stations_greedy(
        route_coords, stations, start_battery, total_distance_km, reverse,
    )


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
        "recommended_out": _recommend_stations(
            route_coords, stations, start_battery, distance, reverse=False
        ),
        "recommended_home": _recommend_stations(
            route_coords, stations, arrival, distance, reverse=True
        ),
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
            charging_list.append(f"**{ordered[i][0].split(' - ')[0]}** \u2014 {ordered[i][0].split(' - ', 1)[-1]}")
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
    table = "| Leg | From → To | Distance | Arrival Battery |\n"
    table += "|-----|-----------|----------|-----------------|\n"
    table += "\n".join(leg_rows)

    charging_md = ""
    if charging_list:
        # No dash prefix, items start on a new line after the heading
        charging_md = "\n\n**Charging stations used:**\n\n" + "\n".join(charging_list)

    summary = (
        f"\n\n**Trip summary:**\n\n{total_dist:.1f} km | "
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