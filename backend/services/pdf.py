"""Markdown assembly and PDF generation via pandoc + LaTeX."""

import os
import re
import shutil
import tempfile
from datetime import datetime

import httpx
import pypandoc

from .. import config
from . import cover_images as cover_svc
from . import geo


def _fetch_city_cover_image(city: str, save_dir: str) -> str | None:
    """Legacy fallback: auto-fetch a Wikimedia image. Uses cover_images module."""
    headers = {"User-Agent": "DBGTripPlanner/1.0 (trip planner brochure generator; dirk.brokken.6208@gmail.com)"}
    search_terms = [
        f"{city} city skyline",
        f"{city} cityscape landmark",
        f"{city} cathedral aerial",
    ]
    for query in search_terms:
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": "6",  # File namespace
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
            if not pages:
                continue

            for page in pages:
                title = page.get("title", "")
                if not title or "icon" in title.lower():
                    continue
                # File:Some_City_Skyline.jpg -> Some_City_Skyline.jpg
                filename = title.replace("File:", "", 1).replace(" ", "_")
                file_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
                # Follow redirects to get the actual image
                img_resp = httpx.get(file_url, follow_redirects=True, timeout=15, headers=headers)
                if img_resp.status_code != 200:
                    continue
                content_type = img_resp.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    continue
                ext = os.path.splitext(filename)[1] or ".jpg"
                dest = os.path.join(save_dir, f"cover_city{ext}")
                with open(dest, "wb") as f:
                    f.write(img_resp.content)
                return dest
        except Exception as e:
            print(f"Wikimedia search for '{query}' failed: {e}")
            continue
    return None


def _screenshot_map_html(html_content: str, save_dir: str, filename: str = "map_restaurants.png") -> str | None:
    """Render a Folium HTML map to a PNG screenshot using headless Chromium + Playwright.

    Returns the path to the saved PNG, or None on failure.
    """
    if not html_content or not html_content.strip():
        return None
    try:
        from playwright.sync_api import sync_playwright

        png_path = os.path.join(save_dir, filename)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": config.MAP_SCREENSHOT_WIDTH, "height": config.MAP_SCREENSHOT_HEIGHT},
                device_scale_factor=2,
            )
            page.set_content(html_content, wait_until="networkidle")
            page.wait_for_timeout(2000)
            page.screenshot(path=png_path, full_page=False)
            browser.close()
        return png_path if os.path.exists(png_path) else None
    except Exception as e:
        print(f"Map screenshot failed: {e}")
        return None


def build_markdown(data: dict) -> str:
    """Assemble all brochure sections into a single markdown document.

    Sections: City Guide, Tourist Office, Hotel, Restaurants, Journey, Planner.
    """
    sections = []

    # City Guide
    guide = data.get("city_guide", "")
    guide = _remove_first_title(guide)  # Remove the # title so we can add it ourselves
    sections.append(f"# City Guide\n\n{guide}")

    # Tourist Office
    to_office = data.get("tourist_office", "")
    sections.append(f"# Tourist Office\n\n{to_office}")

    # Hotel
    hotel = data.get("hotel", "")
    sections.append(f"# Hotel\n\n{hotel}")

    # Restaurants
    restaurants = data.get("restaurants", "")
    sections.append(f"# Restaurants\n\n{restaurants}")

    # Journey
    journey_out = data.get("journey_out", "")
    journey_home = data.get("journey_home", "")
    sections.append(f"# Journey\n\n## Outbound Journey\n\n{journey_out}\n\n## Return Journey\n\n{journey_home}")

    # Planner
    planner = data.get("planner", "")
    sections.append(f"# Planner\n\n{planner}")

    doc = "\n\n".join(sections)

    # Cleanup
    doc = _emoji_strip(doc)
    doc = _html_links_to_md(doc)
    doc = _sanitize_for_pandoc(doc)
    doc = _clean_markdown(doc)

    return doc


def generate_pdf(
    markdown_text: str,
    city: str,
    country: str,
    cover_image_path: str | None = None,
    restaurant_map_html: str | None = None,
    hotel_photo_url: str | None = None,
) -> str:
    """Convert markdown to PDF using pandoc + LaTeX template.

    If no cover_image_path is given, auto-fetches a city photo from
    Wikimedia Commons.  If restaurant_map_html is given, renders it as
    a PNG and embeds it in the Planner section.

    Returns path to generated PDF file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ensure Weekend_Guides directory exists
    guides_dir = config.WEEKEND_GUIDES_DIR
    os.makedirs(guides_dir, exist_ok=True)

    # City-based filename
    safe_city = re.sub(r"[^a-zA-Z0-9]+", "_", city).strip("_").lower()
    safe_country = re.sub(r"[^a-zA-Z0-9]+", "_", country).strip("_").lower()
    output_pdf = os.path.join(
        guides_dir,
        f"weekend_guide_{safe_city}_{safe_country}_{timestamp}.pdf",
    )

    date_str = datetime.now().strftime("%B %d, %Y")
    yaml_header = f"""---
title: "{city} Weekend Travel Guide"
date: "{date_str}"
citytitle: "{city} Weekend Travel Guide"
---


"""

    full_md = yaml_header + markdown_text

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "travel_template.tex")
    logo_path = os.path.join(os.path.dirname(__file__), "..", "static", "logo.svg")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Take restaurant map screenshot into tmpdir
        map_markdown = ""
        if restaurant_map_html:
            map_png = _screenshot_map_html(restaurant_map_html, tmpdir, "map_restaurants.png")
            if map_png and os.path.exists(map_png):
                # Copy next to output PDF so xelatex can find it
                map_out_name = f"map_{safe_city}_{timestamp}.png"
                map_out_path = os.path.join(guides_dir, map_out_name)
                shutil.copy(map_png, map_out_path)
                map_markdown = (
                    "\n\n## Map\n\n"
                    + r"\begin{figure}[htbp]" + "\n"
                    + r"\centering" + "\n"
                    + r"\includegraphics[width=0.85\textwidth]{" + map_out_path + "}\n"
                    + r"\caption{Restaurant locations.}" + "\n"
                    + r"\end{figure}"
                )# Hotel photo: download into tmpdir
        hotel_photo_md = ""
        if hotel_photo_url:
            try:
                resp = httpx.get(hotel_photo_url, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "image/jpeg")
                    ext = ".png" if "png" in ct else ".jpg"
                    hotel_img_local = os.path.join(tmpdir, f"hotel{ext}")
                    with open(hotel_img_local, "wb") as f:
                        f.write(resp.content)
                    # Copy next to output PDF so xelatex can find it
                    hotel_out_name = f"hotel_{safe_city}_{timestamp}{ext}"
                    hotel_out_path = os.path.join(guides_dir, hotel_out_name)
                    shutil.copy(hotel_img_local, hotel_out_path)
                    hotel_photo_md = (
                        "\n\n"
                        + r"\begin{center}" + "\n"
                        + r"\includegraphics[width=0.7\textwidth]{" + hotel_out_path + "}" + "\n"
                        + r"\end{center}"
                    )
                    print(f"Hotel photo saved: {hotel_out_path} ({len(resp.content)} bytes)")
            except Exception as e:
                print(f"WARNING: Hotel photo download failed: {e} — skipping hotel photo in PDF")

        # Build the markdown file in tmpdir
        if map_markdown:
            full_md = full_md.rstrip() + map_markdown
        if hotel_photo_md:
            # Insert photo before **Overview** heading in Hotel section
            full_md = full_md.replace("**Overview**", hotel_photo_md + "\n\n**Overview**", 1)

        md_file = os.path.join(tmpdir, "guide.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(full_md)
        # Debug: save markdown alongside PDF
        debug_md = os.path.join(guides_dir, f"guide_{safe_city}_{timestamp}.md")
        with open(debug_md, "w", encoding="utf-8") as f:
            f.write(full_md)

        extra_args = [
            "--standalone",
            "--pdf-engine=xelatex",
            f"--template={template_path}",
            "--toc",
            "--toc-depth=2",
            "--number-sections",
            "--wrap=none",
            f"--resource-path={tmpdir}",
        ]

        # Logo
        if os.path.exists(logo_path):
            # Convert SVG to PNG for LaTeX compatibility (SVG lacks BoundingBox)
            try:
                import cairosvg
                logo_png = os.path.join(tmpdir, "logo.png")
                cairosvg.svg2png(url=logo_path, write_to=logo_png, output_width=128, output_height=128)
                logo_dest = logo_png
            except Exception:
                logo_dest = os.path.join(tmpdir, "logo.svg")
                shutil.copy(logo_path, logo_dest)
            extra_args.append(f"--variable=logo:{logo_dest}")

        # Cover image
        cover_path = cover_image_path
        if cover_path and (cover_path.startswith("http://") or cover_path.startswith("https://")):
            downloaded = cover_svc.download_image(cover_path, tmpdir)
            if downloaded:
                cover_path = downloaded
            else:
                cover_path = None
        if not cover_path or not os.path.exists(cover_path):
            fetched = _fetch_city_cover_image(city, tmpdir)
            if fetched:
                cover_path = fetched

        if cover_path and os.path.exists(cover_path):
            img_ext = os.path.splitext(cover_path)[1]
            if not img_ext:
                img_ext = ".jpg"
            img_dest = os.path.join(tmpdir, f"cover_image{img_ext}")
            shutil.copy(cover_path, img_dest)
            extra_args.append(f"--variable=cover-image:{img_dest}")

        pypandoc.convert_file(
            md_file, "pdf", format="markdown",
            outputfile=output_pdf, extra_args=extra_args,
        )

    return output_pdf


def _remove_first_title(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _html_links_to_md(html_text: str) -> str:
    """Convert <a href='url'>text</a> to [text](url)."""
    if not html_text:
        return ""
    def repl(m):
        url = m.group(1).replace("&", "%26")
        label = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        return f"[{label}]({url})"
    return re.sub(
        r'<a\s+href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>',
        repl, html_text, flags=re.IGNORECASE | re.DOTALL,
    )


def _emoji_strip(text: str) -> str:
    """Remove emoji and emoticon characters."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # misc
        "]+", flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _sanitize_for_pandoc(text: str) -> str:
    """Fix patterns that break pandoc."""
    if not text:
        return ""
    text = re.sub(r"^(#{1,6})\s*W\s+", r"\1 W", text, flags=re.MULTILINE)
    text = re.sub(r"^---\s*$", "", text, flags=re.MULTILINE)
    return text


def _clean_markdown(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()