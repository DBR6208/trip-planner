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
                img_resp = httpx.get(file_url, follow_redirects=True, timeout=15)
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
) -> str:
    """Convert markdown to PDF using pandoc + LaTeX template.

    If no cover_image_path is given, auto-fetches a city photo from
    Wikimedia Commons. Returns path to generated PDF file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_pdf = os.path.join(
        config.OUTPUT_DIR,
        f"WeekendGuide_{city}_{country}_{timestamp}.pdf",
    )

    date_str = datetime.now().strftime("%B %d, %Y")
    yaml_header = f"""---
title: "Weekend Guide {city} {country}"
date: "{date_str}"
---


"""

    full_md = yaml_header + markdown_text

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "travel_template.tex")

    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = os.path.join(tmpdir, "guide.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(full_md)

        extra_args = [
            "--standalone",
            "--pdf-engine=xelatex",
            f"--template={template_path}",
            "--toc",
            "--toc-depth=2",
            "--number-sections",
            "--wrap=none",
        ]

        # Auto-fetch cover image if none was provided or the path doesn't exist
        cover_path = cover_image_path
        if cover_path and (cover_path.startswith("http://") or cover_path.startswith("https://")):
            # URL from frontend selection — download it
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
        r'<a\s+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',
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