"""Fetch candidate city cover images from Wikimedia Commons and tourist office websites."""

import os
import re

import httpx


def fetch_cover_images(city: str, tourist_office_website: str | None = None) -> list[dict]:
    """Search for representative city photos from multiple sources.

    Returns list of dicts: [{url, thumb, source, title}]
    """
    results = []
    seen_urls = set()

    # 1. Wikimedia Commons
    wm_results = _search_wikimedia(city)
    for img in wm_results:
        if img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            results.append(img)

    # 2. Tourist office website — scrape for hero/official images
    if tourist_office_website:
        to_results = _scrape_website_images(tourist_office_website, city)
        for img in to_results:
            if img["url"] not in seen_urls:
                seen_urls.add(img["url"])
                results.append(img)

    # Limit to top 10
    return results[:10]


def download_image(url: str, save_dir: str) -> str | None:
    """Download an image URL to save_dir and return the local path."""
    try:
        ext = ".jpg"
        # Try to guess extension from URL
        match = re.search(r"\.(jpe?g|png|gif|webp)(\?|$)", url, re.IGNORECASE)
        if match:
            ext = match.group(1).lower()
            if ext == "jpeg":
                ext = "jpg"

        resp = httpx.get(url, follow_redirects=True, timeout=20)
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


def _search_wikimedia(city: str) -> list[dict]:
    """Search Wikimedia Commons for city images with proper thumbnails."""
    results = []
    search_queries = [
        f"{city} skyline",
        f"{city} cityscape",
        f"{city} aerial",
        f"{city} landmark",
        f"{city} cathedral",
        f"{city} old town",
    ]
    tried = set()

    headers = {
        "User-Agent": "DBGTripPlanner/1.0 (trip planner brochure generator; dirk.brokken.6208@gmail.com)"
    }

    for query in search_queries:
        if len(results) >= 10:
            break
        if query.lower() in tried:
            continue
        tried.add(query.lower())

        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": "6",
                "format": "json",
                "srlimit": 5,
                "srqiprofile": "classic",
            }
            r = httpx.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("search", [])

            # Collect all page titles
            titles = []
            for page in pages:
                title = page.get("title", "")
                if not title or "icon" in title.lower() or "flag" in title.lower() or "logo" in title.lower():
                    continue
                titles.append(title)

            if not titles:
                continue

            # Batch query imageinfo for actual thumbnail URLs
            info_params = {
                "action": "query",
                "titles": "|".join(titles),
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": 400,
                "format": "json",
            }
            info_r = httpx.get(
                "https://commons.wikimedia.org/w/api.php",
                params=info_params,
                headers=headers,
                timeout=15,
            )
            info_r.raise_for_status()
            info_data = info_r.json()
            query_pages = info_data.get("query", {}).get("pages", {})

            for pid, page_data in query_pages.items():
                if pid == "-1":
                    continue
                imageinfo = page_data.get("imageinfo", [])
                if not imageinfo:
                    continue
                ii = imageinfo[0]
                mime = ii.get("mime", "")
                if not mime.startswith("image/"):
                    continue

                results.append({
                    "url": ii.get("url", ""),
                    "thumb": ii.get("thumburl", ii.get("url", "")),
                    "source": "Wikimedia Commons",
                    "title": page_data.get("title", "").replace("File:", "", 1),
                })
        except Exception as e:
            print(f"Wikimedia search '{query}' failed: {e}")
            continue

    return results


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

        # Find all <img> tags
        img_pattern = re.compile(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        found_urls = img_pattern.findall(html)

        # Also look for background-image: url(...) in style attrs and <style> blocks
        bg_pattern = re.compile(
            r'background-image:\s*url\(["\']?([^"\'()]+)["\']?\)',
            re.IGNORECASE,
        )
        bg_urls = bg_pattern.findall(html)

        all_img_urls = found_urls + bg_urls

        # Filter and rank
        for img_url in all_img_urls:
            if len(results) >= 5:
                break

            # Resolve relative URLs
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(website_url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"

            if not img_url.startswith("http"):
                continue

            # Skip small icons, logos, tracking pixels
            if any(icon in img_url.lower() for icon in [
                "icon", "logo", "favicon", "pixel", "banner", "spacer",
                "1x1", "blank.gif", "transparent",
            ]):
                continue

            # Prefer larger-looking images (containing common hero keywords)
            keywords = ["hero", "header", "banner", "slide", "gallery", "photo",
                        "city", city.lower(), "landscape", "skyline", "panorama",
                        "main", "top", "bg-", "background"]
            score = sum(1 for kw in keywords if kw in img_url.lower())

            if score >= 1:
                # Build a thumbnail URL (remove query strings for thumb)
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
