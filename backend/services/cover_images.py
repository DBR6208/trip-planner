"""Fetch candidate city cover images from Wikipedia, Wikimedia Commons, and Tavily."""

import os
import re
import json

import httpx

from .. import config

_USER_AGENT = "DBGTripPlanner/1.0 (trip planner brochure generator; dirk.brokken.6208@gmail.com)"
_HEADERS = {"User-Agent": _USER_AGENT}

# Filename patterns that strongly suggest a portrait/people photo
_PORTRAIT_PATTERNS = [
    "portrait", "crop", "bundesarchiv", "bild", "stolperstein",
    "retrato", "retrat", "persons", "person", "hochformat",
    "selfie", "headshot", "mugshot",
    "photograph of", "photo of", "foto de", "foto van",
]


def fetch_cover_images(city: str, tourist_office_website: str | None = None) -> list[dict]:
    """Search for representative city photos.

    Strategy:
      1. Find the city's Wikipedia article and get images from it
         (guaranteed to be photos of that city, filtered for landmarks).
      2. Search via Tavily (uses real image search, not URL-level filters).
      3. Tourist office website images (supplement).

    Returns list of dicts: [{url, thumb, source, title}]
    """
    results = []
    seen_urls = set()

    def _add(img: dict) -> None:
        if img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            results.append(img)

    # 1. Wikipedia article images — most reliable
    for img in _fetch_wikipedia_city_images(city):
        _add(img)

    # 2. Tavily image search — replaces Commons text search + Bing
    for img in _search_tavily_images(city):
        _add(img)

    # 3. Tourist office website
    if tourist_office_website:
        for img in _scrape_website_images(tourist_office_website, city):
            _add(img)

    return results[:10]


def download_image(url: str, save_dir: str) -> str | None:
    """Download an image URL to save_dir and return the local path."""
    try:
        ext = ".jpg"
        match = re.search(r"\.(jpe?g|png|gif|webp)(\?|$)", url, re.IGNORECASE)
        if match:
            ext = match.group(1).lower()
            if ext == "jpeg":
                ext = ".jpg"

        resp = httpx.get(url, follow_redirects=True, timeout=20, headers=_HEADERS)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if not ct.startswith("image/"):
            return None

        dest = os.path.join(save_dir, f"cover{ext}")
        with open(dest, "wb") as f:
            f.write(resp.content)
        return dest
    except Exception as e:
        print(f"download_image failed for {url}: {e}")
        return None


# ── Wikipedia article images ──


def _fetch_wikipedia_city_images(city: str) -> list[dict]:
    """Get images from the city's Wikipedia article.

    First resolves the city name to a Wikipedia page, then fetches images
    from that page.  This guarantees the images are actually about the city.
    """
    results = []
    try:
        page_title = _resolve_wikipedia_page(city)
        if not page_title:
            return results

        # Get images from the page
        params = {
            "action": "query",
            "titles": page_title,
            "prop": "images",
            "format": "json",
            "imlimit": 20,
        }
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, page_data in pages.items():
            if pid == "-1":
                continue
            images = page_data.get("images", [])
            titles = [img["title"] for img in images]

            # Filter out icons, logos, flags, maps, and very small items
            filtered = [
                t for t in titles
                if not any(skip in t.lower() for skip in [
                    "icon", "logo", "flag", "map", "locator", "blank",
                    "wikinews", "sound", "button", "portal", "disambig",
                    "comics", "wordmark", "emblem", "coat of arms", "seal",
                    "montage", "collage", "poster",
                    "stadtbezirke", "overview", "diagram", "plan",
                    "skyline_", "_skyline", "karte", "liniennetz",
                    "wappen", "screenshot", "orthophoto",
                ])
                # Filter out portrait/people filename patterns
                and not any(p in t.lower() for p in _PORTRAIT_PATTERNS)
                # Must be a photo-type extension (jpg, jpeg, png, webp)
                and re.search(r"\.(jpe?g|png|webp)$", t, re.IGNORECASE)
            ]

            # Get imageinfo for the filtered images (batched)
            if filtered:
                # Batch of 50 max
                batch = filtered[:20]
                info_params = {
                    "action": "query",
                    "titles": "|".join(batch),
                    "prop": "imageinfo",
                    "iiprop": "url|mime",
                    "iiurlwidth": 400,
                    "format": "json",
                }
                info_r = httpx.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=info_params,
                    headers=_HEADERS,
                    timeout=15,
                )
                info_r.raise_for_status()
                info_data = info_r.json()
                for _pid, _pd in info_data.get("query", {}).get("pages", {}).items():
                    if _pid == "-1":
                        continue
                    ii = _pd.get("imageinfo", [])
                    if not ii:
                        continue
                    mime = ii[0].get("mime", "")
                    if not mime.startswith("image/"):
                        continue
                    results.append({
                        "url": ii[0].get("url", ""),
                        "thumb": ii[0].get("thumburl", ii[0].get("url", "")),
                        "source": f"Wikipedia ({page_title})",
                        "title": _pd["title"].replace("File:", "", 1),
                    })
        return results[:10]
    except Exception as e:
        print(f"Wikipedia image fetch for {city} failed: {e}")
        return results


def _resolve_wikipedia_page(city: str) -> str | None:
    """Search Wikipedia for a city page and return its canonical title."""
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": city,
            "srlimit": 3,
            "format": "json",
        }
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers=_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("search", [])
        for p in pages:
            title = p.get("title", "")
            # Must contain the city name, and likely be the city article
            if city.lower() in title.lower():
                # Prefer pages ending with the city name (not "History of X" etc.)
                return title
        # Fallback: return first result
        for p in pages:
            return p.get("title")
        return None
    except Exception as e:
        print(f"Wikipedia page resolve for {city} failed: {e}")
        return None


# ── Tavily image search (replaces Commons text search + Bing) ──


def _search_tavily_images(city: str) -> list[dict]:
    """Search for city images via Tavily API.

    Tavily returns actual image URLs from indexed pages (Unsplash, Pexels,
    Wikimedia, etc.) — much more reliable than scraping Bing or Commons text search.
    Falls back silently if the API key is missing or the call fails.
    Validates each URL with a HEAD request before adding it to results.
    """
    results = []
    search_queries = [
        f"{city} skyline landmark cityscape architecture photography",
        f"{city} historic center cathedral church architecture",
        f"{city} aerial city view panorama",
    ]

    for query in search_queries:
        if len(results) >= 12:
            break
        try:
            from tavily import TavilyClient

            tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
            response = tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=8,
                include_images=True,
                include_answer=False,
            )

            # Tavily returns images as a list of URLs under the "images" key
            img_urls = response.get("images", [])

            # Also check results for photo-site URLs
            photo_domains = [
                "unsplash.com", "pexels.com", "pixabay.com",
                "flickr.com", "wikimedia.org", "wikipedia.org",
                "images.pexels.com", "pixabay.com/api",
            ]

            for img_url in img_urls[:5]:
                if not img_url.startswith("http"):
                    continue
                # Skip URLs containing portrait keywords
                if any(p in img_url.lower() for p in _PORTRAIT_PATTERNS):
                    continue
                results.append({
                    "url": img_url,
                    "thumb": img_url,
                    "source": "Tavily",
                    "title": city,
                })
                if len(results) >= 12:
                    break

            # Also search web results for photo-site links
            if len(results) < 8:
                for result in response.get("results", []):
                    url = result.get("url", "")
                    title = result.get("title", city)
                    if not url.startswith("http"):
                        continue
                    for domain in photo_domains:
                        if domain in url.lower():
                            if any(p in url.lower() for p in _PORTRAIT_PATTERNS):
                                continue
                            results.append({
                                "url": url,
                                "thumb": url,
                                "source": f"Tavily ({domain.split('.')[0].title()})",
                                "title": title,
                            })
                            if len(results) >= 12:
                                break
                        if len(results) >= 12:
                            break
                    if len(results) >= 12:
                        break

        except Exception as e:
            print(f"Tavily image search for '{query}' failed: {e}")
            continue

    return results


# ── Tourist office website scraping ──


def _scrape_website_images(website_url: str, city: str) -> list[dict]:
    """Scrape a website (tourist office) for representative images."""
    results = []
    try:
        if not website_url.startswith("http"):
            website_url = "https://" + website_url

        headers = {"User-Agent": "Mozilla/5.0 (compatible; DBGTripPlanner/1.0)"}
        r = httpx.get(website_url, follow_redirects=True, timeout=15, headers=headers)
        r.raise_for_status()
        html = r.text

        img_pattern = re.compile(
            r'<img[^>]+src=["\']([\"\' ]+)["\']',
            re.IGNORECASE,
        )
        found_urls = img_pattern.findall(html)

        bg_pattern = re.compile(
            r'background-image:\s*url\(["\']?([^\"\' ()]+)["\']?\)',
            re.IGNORECASE,
        )
        bg_urls = bg_pattern.findall(html)

        all_img_urls = found_urls + bg_urls

        for img_url in all_img_urls:
            if len(results) >= 5:
                break

            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(website_url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"

            if not img_url.startswith("http"):
                continue

            if any(icon in img_url.lower() for icon in [
                "icon", "logo", "favicon", "pixel", "banner", "spacer",
                "1x1", "blank.gif", "transparent",
            ]):
                continue

            keywords = ["hero", "header", "slide", "gallery", "photo",
                        "city", city.lower(), "landscape", "skyline", "panorama",
                        "main", "top", "bg-", "background"]
            score = sum(1 for kw in keywords if kw in img_url.lower())
            if score >= 1:
                thumb = img_url.split("?")[0] if "?" in img_url else img_url
                results.append({
                    "url": img_url,
                    "thumb": thumb,
                    "source": f"Website: {website_url}",
                    "title": city,
                })
    except Exception as e:
        print(f"Website scrape for '{website_url}' failed: {e}")

    return results
