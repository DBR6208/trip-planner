"""Restaurant search with Dirk Profile matching: 3-5 verified picks per cuisine."""

import json
import re
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import folium
from folium.plugins import BeautifyIcon

from . import geo, llm
from .. import config

# Cuisine color mapping for map markers
CUISINE_COLORS = {
    "Italian": "#C62828",
    "German": "#F57F17",
    "Mediterranean": "#7CB342",
    "Seafood": "#00ACC1",
    "Croatian": "#1565C0",
    "French": "#5C6BC0",
    "Steakhouse": "#6A1B9A",
    "Belgian": "#795548",
}

# Strict filters to eliminate fast food, snackbars, salad/bowl chains, and pure pizza/takeaways
BLOCKED_KEYWORDS = [
    r"\bfast\s*food\b", r"\bkebab\b", r"\bdöner\b", r"\bburger\b", r"\bbowl\b",
    r"\bwrap\b", r"\bpizza\b", r"\bpizzeria\b", r"\bcafe\b", r"\bcafé\b",
    r"\bcoffee\b", r"\btea\b", r"\bbakery\b", r"\bbäckerei\b", r"\bsandwich\b",
    r"\bgrün\b", r"\bgreen\b", r"\bvegan\s*fast\b", r"\bsushi\b", r"\basian\b",
    r"\bsnack\b", r"\bimbi[sß]\b", r"\bhookah\b", r"\bshisha\b",
    # French / Dutch equivalents (Belgium, France, Netherlands, Luxembourg) for
    # fast food, takeaways, bakeries, lunch rooms and tea/ice-cream shops
    r"\bboulangerie\b", r"\bpâtisserie\b", r"\bpatisserie\b", r"\bfriterie\b",
    r"\bfrituur\b", r"\bsnackbar\b", r"\bbakkerij\b", r"\bkoffie\b",
    r"\btake\s*-?away\b", r"\bsandwicherie\b", r"\bsalon\s+de\s+th[ée]\b",
    r"\bbroodjes\w*\b", r"\blunchroom\b", r"\bijssalon\b", r"\beiscaf[ée]\b",
]

BLOCKED_GOOGLE_TYPES = {
    "bakery", "cafe", "meal_takeaway", "fast_food_restaurant", "night_club"
}

# Queries are country-neutral: the app is used in Belgium and its neighbours
# (France, the Netherlands, Germany, Luxembourg). Google Places matches English cuisine terms against
# local-language listings, and the city name is appended to every query. Only
# widely used loanwords (ristorante, trattoria, brasserie, bistro) are kept.
CUISINE_QUERY_MAP = {
    "German": "german restaurant traditional or modern german cuisine",
    "Belgian": "belgian restaurant brasserie",
    "French": "french restaurant brasserie bistro",
    "Italian": "italian restaurant ristorante trattoria",
    "Croatian": "croatian balkan dalmatian restaurant",
    "Steakhouse": "steakhouse grill restaurant",
    "Seafood": "seafood fish restaurant",
    "Mediterranean": "mediterranean spanish portuguese restaurant",
}


# What each label covers, so the LLM does not reject a good fit on a technicality
# (e.g. a Serbian/Bosnian/Balkan grill for "Croatian", tapas for "Mediterranean").
CUISINE_HINTS = {
    "Croatian": "Croatian and the wider Balkan kitchen (Dalmatian, Serbian, Bosnian, cevapi, grilled meats)",
    "German": "traditional OR modern/upscale German and regional cuisine, Wirtshaus, Brauhaus with real dinner menu",
    "Mediterranean": "Spanish, Portuguese, tapas, Provencal and other Mediterranean cooking (not Greek)",
    "Steakhouse": "steak and grill restaurants",
    "Seafood": "fish and seafood restaurants",
    "French": "French cuisine, bistro or brasserie with French menu",
    "Belgian": "Belgian cuisine, brasserie with Belgian specialities",
    "Italian": "Italian restaurants with a broad menu (not pizza/pasta only)",
}

MIN_PER_CUISINE = 3  # only used by the no-LLM fallback
MAX_PER_CUISINE = 5
PLACES_PAGES = 3  # Google text search pages (20 results each) per cuisine query
MAX_POOL = 48  # candidates sent to enrichment and the single LLM pass
MIN_POOL_PER_CUISINE = 5  # best candidates reserved in the pool for each ticked cuisine
# Hard limit from the hotel (2.5 km, set in config); no wider fallback search.
# Beyond a comfortable walk a taxi is acceptable.
MAX_DISTANCE_M = config.WALK_DISTANCE_MAX_METERS


def _clean_restaurant_name(name: str | None) -> str:
    """Remove accidental list numbering returned by a place-search provider."""
    return re.sub(r"^\s*\d+[.)\-:]\s*", "", name or "").strip()


def _clean_restaurant_description(description: str | None) -> str:
    """Remove a copied leading list number from generated restaurant text."""
    return re.sub(r"^\s*\d+[.)\-:]\s*", "", description or "").strip()


def _cuisine_color(cuisine: str) -> str:
    """Get the map marker color for a cuisine type."""
    return CUISINE_COLORS.get(cuisine, "#757575")


def _is_cuisine_excluded(*texts: str | None) -> bool:
    """Check restaurant metadata or evidence for excluded cuisine terms."""
    text = " ".join(part for part in texts if part).casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", text)
        for keyword in config.EXCLUDED_CUISINE_KEYWORDS
    )


def _get_cuisine_evidence(restaurant: dict, city: str | None, cache: dict[str, str]) -> str:
    """Independent Tavily evidence (titles/snippets) about a candidate's cuisine."""
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

        response = TavilyClient(api_key=config.TAVILY_API_KEY).search(
            query=f'"{name}" "{address or city or ""}" restaurant menu cuisine',
            search_depth="basic",
            max_results=3,
            include_answer=False,
        )
        evidence = "\n".join(
            f"{r.get('title', '')} {r.get('content', '')}"
            for r in response.get("results", [])
            if r.get("title") or r.get("content")
        )
    except Exception as exc:
        print(f"Cuisine verification failed for '{name}': {exc}")
        evidence = ""
    cache[cache_key] = evidence
    return evidence


def _is_blocked(name: str, types: list[str]) -> bool:
    name_lower = name.lower()
    for pat in BLOCKED_KEYWORDS:
        if re.search(pat, name_lower):
            return True
    if any(t in BLOCKED_GOOGLE_TYPES for t in types) and "restaurant" not in types:
        return True
    return False


def _get_place_details(place_id: str) -> dict:
    """Fetch website, phone, opening hours, and review snippets from Google."""
    if not place_id:
        return {}
    try:
        details = geo.gmaps().place(
            place_id=place_id,
            fields=[
                "website",
                "formatted_phone_number",
                "permanently_closed",
                "price_level",
                "opening_hours",
                "editorial_summary",
                "reviews",
            ],
        )
        res = details.get("result", {})
        review_texts = [
            r.get("text", "")[:250]
            for r in res.get("reviews", [])[:3]
            if r.get("text")
        ]
        return {
            "website": res.get("website"),
            "phone_number": res.get("formatted_phone_number"),
            "permanently_closed": res.get("permanently_closed", False),
            "price_level": res.get("price_level"),
            "editorial_summary": res.get("editorial_summary", {}).get("overview", ""),
            "review_snippets": review_texts,
        }
    except Exception:
        return {}


_GENERIC_NAME_WORDS = {
    "restaurant", "ristorante", "pizzeria", "trattoria", "bistro", "brasserie",
    "cafe", "bar", "hotel", "the", "der", "die", "das", "de", "la", "le", "les",
    "het", "een", "en", "und", "and", "am", "im", "zum", "zur", "bei", "da",
    "di", "il", "el", "chez", "au", "aux", "du", "des",
}


def _normalize_text(text: str | None) -> str:
    """Lowercase, strip accents and punctuation: "Osnabrück" -> "osnabruck"."""
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _brand_key(name: str, city: str | None) -> str:
    """Name without generic words and city: all branches share one key."""
    tokens = _normalize_text(name).split()
    city_tokens = _normalize_text(city).split()
    city_prefix = city_tokens[0][:5] if city_tokens else ""
    kept = [
        t for t in tokens
        if t not in _GENERIC_NAME_WORDS
        and not (city_prefix and len(t) >= 5 and t.startswith(city_prefix))
    ]
    return " ".join(kept[:2]) or " ".join(tokens)


def _is_known_chain(name: str) -> bool:
    text = _normalize_text(name)
    return any(
        re.search(rf"\b{re.escape(_normalize_text(chain))}\b", text)
        for chain in config.KNOWN_CHAINS
    )


def _is_food_place(types: list[str]) -> bool:
    """Accept restaurants, and places typed only as food/bar (no 'restaurant')."""
    return "restaurant" in types or "food" in types


def _fetch_places(query: str, hotel_coords: tuple[float, float]) -> list[dict]:
    """Text search with pagination (up to PLACES_PAGES pages of 20 results)."""
    results: list[dict] = []
    token = None
    for _ in range(PLACES_PAGES):
        res = None
        # A next_page_token needs a moment before Google accepts it.
        for _attempt in range(3 if token else 1):
            try:
                if token:
                    time.sleep(2.0)
                    res = geo.gmaps().places(page_token=token)
                else:
                    res = geo.gmaps().places(
                        query=query, location=hotel_coords, radius=MAX_DISTANCE_M
                    )
                break
            except Exception:
                res = None
        if res is None:
            break
        results.extend(res.get("results", []))
        token = res.get("next_page_token")
        if not token:
            break
    return results


def _gather_pool(
    cuisines: list[str], hotel_coords: tuple[float, float], city: str | None
) -> dict[str, dict]:
    """Run one search per ticked cuisine and merge by place_id.

    The search a place was found by is only a weak hint (found_by); the real
    cuisine is decided later from evidence.
    """
    raw: dict[str, dict] = {}
    for cuisine in cuisines:
        query_base = CUISINE_QUERY_MAP.get(cuisine, f"{cuisine} restaurant")
        query = f"{query_base} in {city}" if city else query_base
        for p in _fetch_places(query, hotel_coords):
            pid = p.get("place_id")
            if not pid:
                continue
            entry = raw.setdefault(pid, {"place": p, "found_by": []})
            if cuisine not in entry["found_by"]:
                entry["found_by"].append(cuisine)
    return raw


def _prefilter_pool(
    raw: dict[str, dict], hotel_coords: tuple[float, float], city: str | None
) -> list[dict]:
    """Cheap generic filters on search results (no extra API calls)."""
    # A brand that appears more than once in the results has several branches.
    brand_counts = Counter(
        _brand_key(_clean_restaurant_name(e["place"].get("name", "")), city)
        for e in raw.values()
    )
    candidates = []
    for pid, entry in raw.items():
        p = entry["place"]
        name = _clean_restaurant_name(p.get("name", ""))
        types = p.get("types", [])

        if not _is_food_place(types):
            continue
        if _is_blocked(name, types) or _is_cuisine_excluded(name):
            continue
        if _is_known_chain(name) or brand_counts[_brand_key(name, city)] > 1:
            continue

        rating = p.get("rating", 0.0)
        reviews = p.get("user_ratings_total", 0)
        if reviews < config.REVIEW_MINIMUM or rating < 4.1:
            continue

        loc = p.get("geometry", {}).get("location", {})
        lat, lng = loc.get("lat"), loc.get("lng")
        if not lat or not lng:
            continue
        dist_m = geo.geodesic_distance(hotel_coords[0], hotel_coords[1], lat, lng)
        if dist_m > MAX_DISTANCE_M:
            continue

        candidates.append({
            "place_id": pid,
            "name": name,
            "address": p.get("formatted_address", "N/A"),
            "latitude": lat,
            "longitude": lng,
            "rating": rating,
            "user_ratings_total": reviews,
            "distance_meters": dist_m,
            "distance_km": round(dist_m / 1000, 2),
            "types": types,
            "found_by": entry["found_by"],
        })

    candidates.sort(key=lambda x: (-x["rating"], x["distance_meters"]))

    # Reserve pool slots per cuisine so a niche cuisine with few strong hits
    # (e.g. Croatian) is not crowded out by broad ones (German, Mediterranean).
    pool: list[dict] = []
    seen: set[str] = set()
    cuisines = list(dict.fromkeys(c for e in raw.values() for c in e["found_by"]))
    for cuisine in cuisines:
        taken = 0
        for cand in candidates:
            if taken >= MIN_POOL_PER_CUISINE:
                break
            if cuisine in cand["found_by"] and cand["place_id"] not in seen:
                pool.append(cand)
                seen.add(cand["place_id"])
                taken += 1
    for cand in candidates:
        if len(pool) >= MAX_POOL:
            break
        if cand["place_id"] not in seen:
            pool.append(cand)
            seen.add(cand["place_id"])
    pool.sort(key=lambda x: (-x["rating"], x["distance_meters"]))
    return pool[:MAX_POOL]


def _enrich_pool(
    pool: list[dict],
    hotel_coords: tuple[float, float],
    city: str | None,
    cache: dict[str, str],
) -> list[dict]:
    """Add walking distance, Google details and independent web evidence."""
    for i in range(0, len(pool), 20):  # distance matrix: max 25 destinations
        geo.get_walking_distances(hotel_coords, pool[i:i + 20])

    def _enrich(c: dict) -> dict | None:
        det = _get_place_details(c["place_id"])
        if det.get("permanently_closed"):
            return None
        c.update(det)
        if _is_cuisine_excluded(c.get("website")):
            return None
        c["evidence"] = _get_cuisine_evidence(c, city, cache)[:600]
        return c

    with ThreadPoolExecutor(max_workers=8) as executor:
        enriched = list(executor.map(_enrich, pool))
    return [c for c in enriched if c]


def _select_with_llm(
    pool: list[dict], cuisines: list[str], city: str | None
) -> list[dict]:
    """Classify every candidate and pick the best 0-5 per ticked cuisine.

    The LLM decides the real cuisine from the evidence and rejects chains,
    pizza/pasta-only menus, pubs/bars, fast food and excluded cuisines. It may
    return fewer than MAX_PER_CUISINE, or nothing, for a cuisine: no padding.
    """
    if not pool:
        return []

    items = [
        {
            "place_id": c["place_id"],
            "name": c["name"],
            "address": c["address"],
            "google_types": [
                t for t in c.get("types", [])
                if t not in ("point_of_interest", "establishment")
            ],
            "found_by_search": c.get("found_by", []),
            "walk_duration": c.get("walk_duration", "N/A"),
            "rating": c["rating"],
            "reviews_count": c["user_ratings_total"],
            "website": c.get("website") or "",
            "editorial_summary": c.get("editorial_summary", ""),
            "reviews_sample": c.get("review_snippets", []),
            "web_evidence": c.get("evidence", ""),
        }
        for c in pool
    ]

    prompt = f"""
You are a culinary travel expert curating dinner restaurants in {city or 'the city'} for the "DIRK CULINARY PROFILE".

PROFILE (all criteria must be satisfied):
- Warm, generous, Burgundian evening dining: a sit-down dinner restaurant with a real menu.
- High quality meat, fish, grill or hearty main courses, good portions, good wine or beer selection.
- Well rated, with a solid number of reviews, within comfortable walking distance of the hotel.

REJECT (leave out) a candidate when the evidence shows any of these:
- It belongs to a chain or franchise (several branches, uniform concept), even if the name sounds local.
- The menu is mainly pizza and/or pasta (pizzeria-style or "pasta e pizza" places). An Italian restaurant only qualifies with a broad menu including meat or fish main courses.
- It is mainly a pub, bar, kneipe, cocktail bar or club where food is secondary.
- It is fast food, snack, takeaway, street food, cafe, bakery, lunch or ice-cream place.
- It serves Turkish, Greek, Asian, Chinese, Thai, Indian, Japanese, Middle Eastern, fusion or halal cuisine.
- There is no sign it serves proper dinner.

CUISINES TO FILL (use exactly these labels): {json.dumps(cuisines)}
What each label covers: {json.dumps({c: CUISINE_HINTS.get(c, c) for c in cuisines}, ensure_ascii=False)}

For every kept candidate choose ONE cuisine label from that list: the cuisine the restaurant really serves as its main identity, judged from the name, editorial summary, reviews and web evidence. "found_by_search" is only a weak hint and is often wrong. If a candidate fits none of the labels, leave it out.

CANDIDATES (real places from Google Maps):
{json.dumps(items, indent=1, ensure_ascii=False)}

TASK:
For each cuisine label select up to {MAX_PER_CUISINE} best candidates, best match first. Return fewer when fewer truly qualify, and nothing for a label when none qualify. Never pad a label with candidates that do not fit. Use each candidate at most once. Choose ONLY from the given place_ids; never invent a place.
"why_it_fits" must be ONE short concrete sentence (max 25 words) on food and ambiance; no lead-in, no emoji.

Return ONLY valid JSON:
{{"selected": [{{"place_id": "exact place_id", "cuisine": "one label from the list", "why_it_fits": "one short sentence", "match_score": "9.2/10"}}]}}
"""
    by_pid = {c["place_id"]: c for c in pool}
    selected: list[dict] = []
    per_cuisine: Counter = Counter()
    used: set[str] = set()

    try:
        response_text = llm.generate(prompt, max_tokens=6000)
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        data = json.loads(match.group(0)) if match else json.loads(response_text)
        for item in data.get("selected", []):
            pid = item.get("place_id")
            cuisine = item.get("cuisine")
            if (
                pid in by_pid and pid not in used and cuisine in cuisines
                and per_cuisine[cuisine] < MAX_PER_CUISINE
            ):
                used.add(pid)
                per_cuisine[cuisine] += 1
                selected.append({
                    **by_pid[pid],
                    "cuisine": cuisine,
                    "why_it_fits": item.get("why_it_fits", ""),
                    "match_score": item.get("match_score", ""),
                })
    except Exception as exc:
        print(f"[restaurants] LLM selection failed ({exc}); using fallback")
        return _fallback_selection(pool, cuisines)

    # Present in the order the cuisines were ticked.
    order = {c: i for i, c in enumerate(cuisines)}
    selected.sort(key=lambda r: order.get(r["cuisine"], 99))
    return selected


def _fallback_selection(pool: list[dict], cuisines: list[str]) -> list[dict]:
    """Used only when the LLM call fails: best rated per search hint."""
    selected: list[dict] = []
    used: set[str] = set()
    for cuisine in cuisines:
        count = 0
        for c in pool:
            if count >= MIN_PER_CUISINE:
                break
            if (
                c["place_id"] in used
                or cuisine not in c.get("found_by", [])
                or _is_cuisine_excluded(c.get("evidence"))
            ):
                continue
            used.add(c["place_id"])
            count += 1
            selected.append({
                **c,
                "cuisine": cuisine,
                "why_it_fits": f"Well rated {cuisine} restaurant near the hotel.",
                "match_score": "",
            })
    return selected


def find_restaurants(
    hotel_coords: tuple[float, float],
    cuisines: list[str],
    city: str | None = None,
) -> list[dict]:
    """Find verified restaurants for the ticked cuisines.

    Pipeline: wide paginated search -> generic filters (food place, blocked
    words, chains, rating, 2.5 km) -> enrichment (details, web evidence) -> one
    LLM pass that classifies the real cuisine and rejects poor fits.
    """
    cuisines = [c for c in dict.fromkeys(cuisines) if c in CUISINE_COLORS]
    if not cuisines:
        return []

    raw = _gather_pool(cuisines, hotel_coords, city)
    pool = _prefilter_pool(raw, hotel_coords, city)
    pool = _enrich_pool(pool, hotel_coords, city, {})
    results = _select_with_llm(pool, cuisines, city)

    # One big prompt lets the model skip a niche cuisine. For every ticked
    # cuisine that came back empty, run a focused pass over the unused
    # candidates that its own search found.
    used_ids = {r["place_id"] for r in results}
    for cuisine in cuisines:
        if any(r["cuisine"] == cuisine for r in results):
            continue
        leftovers = [
            c for c in pool
            if c["place_id"] not in used_ids and cuisine in c.get("found_by", [])
        ]
        extra = _select_with_llm(leftovers, [cuisine], city) if leftovers else []
        for r in extra:
            used_ids.add(r["place_id"])
        results.extend(extra)
    order = {c: i for i, c in enumerate(cuisines)}
    results.sort(key=lambda r: order.get(r["cuisine"], 99))
    print(
        f"[restaurants] found={len(raw)} enriched={len(pool)} "
        f"selected={len(results)} {dict(Counter(r['cuisine'] for r in results))}"
    )

    # Keep the API response small: drop internal working fields.
    for r in results:
        for key in ("types", "found_by", "evidence"):
            r.pop(key, None)
    return results


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
            maps_url = geo.generate_maps_url(r.get("place_id", ""))
            desc = _clean_restaurant_description(r.get("why_it_fits"))[:200]
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
    """Generate a Folium map with hotel marker + cuisine-colored restaurant markers and website links."""
    if not hotel or not hotel.get("latitude"):
        return ""

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
    m = folium.Map(location=(avg_lat, avg_lon), zoom_start=15, tiles="OpenStreetMap")

    # Hotel Marker
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

    # Restaurant Markers
    for r in restaurants:
        lat = r.get("latitude")
        lng = r.get("longitude")
        if lat is None or lng is None:
            continue

        cuisine = r.get("cuisine", "")
        color = _cuisine_color(cuisine)

        popup_links = []
        maps_url = geo.generate_maps_url(r.get("place_id", ""))
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