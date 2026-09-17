"""Markdown assembly and PDF generation via pandoc + LaTeX."""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import httpx
import pypandoc

from .. import config
from . import cover_images as cover_svc
from . import geo


if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    try:
        # Playwright launches Chromium through subprocesses on Windows.
        # Some environments switch to a selector loop policy, which cannot
        # create subprocess transports and causes NotImplementedError.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def _latex_escape(text: str) -> str:
    """Escape text for safe use inside LaTeX content."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def _latex_url(url: str) -> str:
    """Wrap a URL so it can be used safely inside \\href."""
    return r"\detokenize{" + url + "}"


def _fetch_city_cover_image(city: str, save_dir: str) -> str | None:
    """Fallback: use Tavily to find a city cover image, download it, return path."""
    try:
        from tavily import TavilyClient
        from .. import config

        tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
        query = f"{city} skyline landmark cityscape architecture photography"
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_images=True,
            include_answer=False,
        )

        img_urls = response.get("images", [])
        for img_url in img_urls[:5]:
            if not img_url.startswith("http"):
                continue
            try:
                resp = httpx.get(img_url, follow_redirects=True, timeout=15, headers={
                    "User-Agent": "DBGTripPlanner/1.0 (trip planner brochure generator; dirk.brokken.6208@gmail.com)"
                })
                if resp.status_code != 200:
                    continue
                ct = resp.headers.get("content-type", "")
                if ct not in {"image/jpeg", "image/png"}:
                    continue
                ext = ".jpg"
                m = re.search(r"\.(jpe?g|png|gif|webp)(\?|$)", img_url, re.IGNORECASE)
                if m:
                    ext = m.group(1).lower()
                    if ext == "jpeg":
                        ext = ".jpg"
                if ext not in {".jpg", ".jpeg", ".png"}:
                    ext = ".jpg" if ct == "image/jpeg" else ".png"
                dest = os.path.join(save_dir, f"cover_city{ext}")
                with open(dest, "wb") as f:
                    f.write(resp.content)
                print(f"Cover image downloaded via Tavily: {img_url}")
                return dest
            except Exception:
                continue
    except Exception as e:
        print(f"Tavily cover image search for {city} failed: {e}")

    return None


def _screenshot_map_html(html_content: str, save_dir: str, filename: str = "map_restaurants.png") -> str | None:
    """Render a Folium HTML map to a PNG screenshot using headless Chromium + Playwright.

    Returns the path to the saved PNG, or None on failure.
    """
    if not html_content or not html_content.strip():
        return None
    try:
        from playwright.sync_api import sync_playwright

        def _browser_executable() -> str | None:
            candidates = [
                os.environ.get("CHROME_PATH"),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]
            for candidate in candidates:
                if candidate and Path(candidate).exists():
                    return candidate
            return None

        png_path = os.path.join(save_dir, filename)
        with sync_playwright() as p:
            browser = None
            browser_path = _browser_executable()
            try:
                if browser_path:
                    browser = p.chromium.launch(headless=True, executable_path=browser_path)
                else:
                    browser = p.chromium.launch(headless=True)
            except Exception:
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass
                if browser_path:
                    raise
                raise
            page = browser.new_page(
                viewport={"width": config.MAP_SCREENSHOT_WIDTH, "height": config.MAP_SCREENSHOT_HEIGHT},
                device_scale_factor=2,
            )
            # Folium maps keep network activity alive while tiles load, so
            # waiting for "networkidle" can stall indefinitely. Load the DOM,
            # then give Leaflet time to render the map and tiles.
            page.set_content(html_content, wait_until="load")
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

    def new_page_section(title: str, body: str) -> str:
        """Start a section on a new page in the generated PDF."""
        return f"\\newpage\n\n# {title}\n\n{body}"

    # City Guide
    guide = data.get("city_guide", "")
    guide = _remove_first_title(guide)  # Remove the # title so we can add it ourselves
    sections.append(f"# City Guide\n\n{guide}")

    # Tourist Office
    to_office = data.get("tourist_office", "")
    sections.append(f"# Tourist Office\n\n{to_office}")

    # Hotel
    hotel = data.get("hotel", "")
    sections.append(new_page_section("Hotel", "<!-- HOTEL_PHOTO -->\n\n" + hotel))

    # Restaurants
    restaurants = data.get("restaurants", "")
    sections.append(new_page_section("Restaurants", "<!-- RESTAURANT_MAP -->\n\n" + restaurants))

    # Journey
    journey_out = data.get("journey_out", "")
    journey_home = data.get("journey_home", "")
    sections.append(
        new_page_section(
            "Journey",
            f"## Outbound Journey\n\n{journey_out}\n\n## Return Journey\n\n{journey_home}",
        )
    )

    # Planner
    planner = data.get("planner", "")
    sections.append(new_page_section("Planner", planner))

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
    restaurant_data: list[dict] | None = None,
) -> tuple[str, str]:
    """Convert markdown to PDF using pandoc + LaTeX template.

    If no cover_image_path is given, auto-fetches a city photo from
    Wikimedia Commons.  If restaurant_map_html is given, renders it as
    a PNG and embeds it in the Restaurants section (right after the
    ## Restaurants header, no caption).

    Returns tuple of (pdf_path, final_markdown_with_images)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ensure temp directory exists
    guides_dir = config.TEMP_GUIDES_DIR
    os.makedirs(guides_dir, exist_ok=True)

    # City-based filename
    safe_city = re.sub(r"[^a-zA-Z0-9]+", "_", city).strip("_").lower()
    safe_country = re.sub(r"[^a-zA-Z0-9]+", "_", country).strip("_").lower()
    output_pdf = os.path.join(
        guides_dir,
        f"weekend_guide_{safe_city}_{safe_country}_{timestamp}.pdf",
    )

    date_str = datetime.now().strftime("%B %d, %Y")
    
    # Capitalize city name for title
    city_title = city[0].upper() + city[1:] if city else "Weekend Travel Guide"
    
    yaml_header = f"""---
title: "{city_title} Weekend Travel Guide"
date: "{date_str}"
citytitle: "{city_title} Weekend Travel Guide"
---


"""
    
    # Strip existing YAML header from markdown_text to avoid duplicates
    md_stripped = markdown_text
    if markdown_text.startswith("---"):
        parts = markdown_text.split("---", 2)
        if len(parts) >= 3:
            md_stripped = parts[2].strip() + "\n"
    
    full_md = yaml_header + md_stripped

    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "travel_template.tex")
    logo_path = os.path.join(os.path.dirname(__file__), "..", "static", "logo.svg")

    def _markdown_path(path: str) -> str:
        """Normalize a filesystem path for Pandoc markdown on all platforms."""
        return os.path.abspath(path).replace("\\", "/")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Take restaurant map screenshot into tmpdir
        map_markdown = ""
        if restaurant_map_html:
            map_png = _screenshot_map_html(restaurant_map_html, tmpdir, "map-restaurants.png")
            if map_png and os.path.exists(map_png):
                # Keep the map in the temp directory and reference it by name.
                # A hyphenated filename avoids Pandoc escaping issues.
                map_markdown = _build_map_markdown(os.path.basename(map_png))
        hotel_out_path_tex = None
        hotel_md_ref = None
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
                    hotel_out_path_tex = _markdown_path(hotel_out_path)
                    hotel_md_ref = os.path.basename(hotel_img_local)
                    print(f"Hotel photo saved: {hotel_out_path} ({len(resp.content)} bytes)")
            except Exception as e:
                print(f"WARNING: Hotel photo download failed: {e} — skipping hotel photo in PDF")

        # Build the markdown file in tmpdir
        if map_markdown:
            # Insert restaurant map at the top of the Restaurants section.
            full_md = full_md.replace(
                "<!-- RESTAURANT_MAP -->",
                map_markdown,
                1,
            )
        else:
            full_md = full_md.replace("<!-- RESTAURANT_MAP -->", "", 1)
        if hotel_out_path_tex:
            full_md = full_md.replace(
                "<!-- HOTEL_PHOTO -->",
                f"\n\n![](<{hotel_md_ref or hotel_out_path_tex}>){{width=45%}}\n\n",
                1,
            )
        else:
            full_md = full_md.replace("<!-- HOTEL_PHOTO -->", "", 1)

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
                logo_dest = _markdown_path(logo_png)
            except Exception as e:
                print(f"WARNING: Logo conversion failed: {e} — skipping logo in PDF")
                logo_dest = None
            if logo_dest:
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
            if img_ext.lower() not in {".jpg", ".jpeg", ".png"}:
                print(f"Skipping unsupported cover image format: {cover_path}")
                cover_path = None
            else:
                # Avoid underscores here: Pandoc can escape them when injecting
                # template variables, which makes XeLaTeX look for cover\_image.*.
                img_dest = os.path.join(tmpdir, f"cover-image{img_ext}")
                shutil.copy(cover_path, img_dest)
                extra_args.append(f"--variable=cover-image:{_markdown_path(img_dest)}")

        try:
            pypandoc.convert_file(
                md_file, "pdf", format="markdown",
                outputfile=output_pdf, extra_args=extra_args,
            )
        except Exception as e:
            # Preserve the pandoc error output in the server logs so we can
            # see the exact image or LaTeX failure on the next run.
            print(f"Pandoc conversion failed for {md_file}: {e}")
            raise

    # Return both the PDF path AND the final markdown (with images injected)
    # so the frontend can display the exact markdown used to generate the PDF
    return output_pdf, full_md


def compress_pdf(pdf_path: str) -> None:
    """Compress a PDF in-place using Ghostscript.

    Reduces file size dramatically (images downsampled, font subsetting, etc.).
    Falls back silently if Ghostscript is unavailable or compression fails.
    """
    try:
        tmp = pdf_path + ".tmp"
        result = subprocess.run(
            [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.7",
                "-dPDFSETTINGS=/ebook",
                "-dNOPAUSE", "-dQUIET", "-dBATCH",
                "-dDownsampleColorImages=true",
                "-dColorImageResolution=150",
                "-dDownsampleGrayImages=true",
                "-dGrayImageResolution=150",
                "-dDownsampleMonoImages=true",
                "-dMonoImageResolution=150",
                f"-sOutputFile={tmp}",
                pdf_path,
            ],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, pdf_path)
        elif os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        # If compression fails, keep the original
        pass


def _remove_first_title(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _build_map_markdown(map_path: str) -> str:
    """Build markdown for restaurant map (no figure caption, 100% width) + cuisine legend below."""
    map_file = Path(map_path).name
    legend = (
        "\\begin{center}\n"
        "\\begin{tabular}{ll@{\\hspace{12pt}}ll@{\\hspace{12pt}}ll}\n"
        "\\textbf{Cuisine} & & &  \\\\[2pt]\n"
        "\n"
        "\\textcolor[HTML]{2E7D32}{\\large\\textbullet} Local &\n"
        "\\textcolor[HTML]{C62828}{\\large\\textbullet} Italian &\n"
        "\\textcolor[HTML]{1565C0}{\\large\\textbullet} Croatian  \\\\\n"
        "\n"
        "\\textcolor[HTML]{E65100}{\\large\\textbullet} Grill &\n"
        "\\textcolor[HTML]{6A1B9A}{\\large\\textbullet} Steakhouse  &\n"
        "\\textcolor[HTML]{00838F}{\\large\\textbullet} Seafood\\\\\n"
        "\\end{tabular}\n"
        "\\end{center}\n"
    )
    return (
        "\n\n![](" + map_file + "){ width=100% }\n\n"
        + legend
    )


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
