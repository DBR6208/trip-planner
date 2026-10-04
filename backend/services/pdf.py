"""Markdown assembly and PDF generation via pandoc + LaTeX."""

import asyncio
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import httpx
import pypandoc

from .. import config
from . import cover_images as cover_svc
from . import restaurants as restaurants_svc

# Fixed brochure layout values (previously adjustable through the layout chat).
LAYOUT_SETTINGS = {
    "hotel_image_alignment": "center",
    "hotel_image_width_percent": 45,
    "restaurant_map_width_percent": 100,
    "keep_restaurant_cards_together": True,
    "restaurant_heading_gap_pt": 14,
    "restaurant_card_gap_pt": 12,
}


if os.name == "nt" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    try:
        # Playwright launches Chromium through subprocesses on Windows.
        # Some environments switch to a selector loop policy, which cannot
        # create subprocess transports and causes NotImplementedError.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def _safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_").lower() or "brochure"


def source_dir_for(city: str) -> str:
    """Persistent, hand-editable source folder for a city's brochure."""
    return os.path.join(config.WEEKEND_GUIDES_DIR, "source", _safe_name(city))


@contextmanager
def _source_workdir(city: str):
    """Fresh persistent folder for this brochure's source files and images.

    Unlike a temp dir it is kept after the PDF is built, so the generated
    .typ/.tex and its images can be edited by hand and rebuilt later.
    """
    path = source_dir_for(city)
    if os.path.isdir(path):
        # Keep the previous version (one level) so hand edits are never lost
        # when the PDF is regenerated from the Markdown.
        backup = path + "_previous"
        shutil.rmtree(backup, ignore_errors=True)
        shutil.move(path, backup)
    os.makedirs(path, exist_ok=True)
    yield path


def find_source_file(city: str) -> str | None:
    """Return the editable brochure.typ / brochure.tex for a city, if any."""
    folder = source_dir_for(city)
    for name in ("brochure.typ", "brochure.tex"):
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate):
            return candidate
    return None


def rebuild_from_source(city: str) -> tuple[str, str]:
    """Compile the (possibly hand-edited) brochure source into a new PDF.

    Returns (pdf_path, source_filename). Raises FileNotFoundError when no
    source exists yet and RuntimeError with the compiler output on errors.
    """
    source = find_source_file(city)
    if not source:
        raise FileNotFoundError(
            "No brochure source found for this city. Generate the PDF first."
        )
    os.makedirs(config.TEMP_GUIDES_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_pdf = os.path.join(
        config.TEMP_GUIDES_DIR, f"weekend_guide_{_safe_name(city)}_{timestamp}.pdf"
    )
    folder = os.path.dirname(source)
    if source.endswith(".typ"):
        _compile_typst(source, output_pdf, folder)
    else:
        _compile_latex(source, output_pdf)
    return output_pdf, os.path.basename(source)


def _compile_latex(tex_file: str, output_pdf: str) -> None:
    """Compile a .tex file with XeLaTeX (two passes for the table of contents)."""
    folder = os.path.dirname(tex_file)
    name = os.path.basename(tex_file)
    log = ""
    for _ in range(2):
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", name],
            cwd=folder, capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        log = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            lines = [ln for ln in log.splitlines() if ln.startswith("!")]
            details = "\n".join(lines[:5]) or log[-1500:]
            raise RuntimeError(f"XeLaTeX compilation failed: {details}")
    built = os.path.splitext(tex_file)[0] + ".pdf"
    if not os.path.exists(built):
        raise RuntimeError("XeLaTeX finished but produced no PDF")
    shutil.copy(built, output_pdf)


def _fetch_city_cover_image(city: str, save_dir: str) -> str | None:
    """Fallback: use Tavily to find a city cover image, download it, return path."""
    try:
        from tavily import TavilyClient

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
        # This HTML comment is visible in CodeMirror for manual editing but
        # hidden by Markdown/HTML previews. It becomes an actual PDF break only
        # inside _prepare_markdown_for_engine().
        return f"<!-- pagebreak -->\n\n# {title}\n\n{body}"

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
    restaurants = _add_brochure_restaurant_pagebreaks(restaurants)
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
    """Convert markdown to PDF using the configured Pandoc renderer.

    If no cover_image_path is given, auto-fetches a city photo from
    Wikimedia Commons.  If restaurant_map_html is given, renders it as
    a PNG and embeds it in the Restaurants section (right after the
    ## Restaurants header, no caption).

    XeLaTeX remains the default renderer so setting ``PDF_ENGINE=xelatex`` is
    an immediate rollback to the existing workflow. Typst is opt-in through
    ``PDF_ENGINE=typst``.

    Returns tuple of (pdf_path, final_markdown_with_images).
    """
    engine = config.PDF_ENGINE
    if engine not in {"xelatex", "typst"}:
        raise ValueError("PDF_ENGINE must be either 'xelatex' or 'typst'")
    layout = LAYOUT_SETTINGS
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

    template_name = "travel_template.tex" if engine == "xelatex" else "travel_template.typ"
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", template_name)
    logo_path = os.path.join(os.path.dirname(__file__), "..", "static", "logo.svg")

    def _markdown_path(path: str) -> str:
        """Normalize a filesystem path for Pandoc markdown on all platforms."""
        return os.path.abspath(path).replace("\\", "/")

    with _source_workdir(city) as tmpdir:
        # Take restaurant map screenshot into the source folder
        map_markdown = ""
        if restaurant_map_html:
            map_png = _screenshot_map_html(restaurant_map_html, tmpdir, "map-restaurants.png")
            if map_png and os.path.exists(map_png):
                # Keep the map in the temp directory and reference it by name.
                # A hyphenated filename avoids Pandoc escaping issues.
                map_markdown = _build_map_markdown(
                    os.path.basename(map_png),
                    engine,
                    layout["restaurant_map_width_percent"],
                    _legend_cuisines(restaurant_data),
                )
        hotel_image_path = None
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
                    # Keep a durable copy beside the output PDF for final brochures.
                    hotel_out_name = f"hotel_{safe_city}_{timestamp}{ext}"
                    hotel_out_path = os.path.join(guides_dir, hotel_out_name)
                    shutil.copy(hotel_img_local, hotel_out_path)
                    hotel_image_path = _markdown_path(hotel_out_path)
                    hotel_md_ref = os.path.basename(hotel_img_local)
                    print(f"Hotel photo saved: {hotel_out_path} ({len(resp.content)} bytes)")
            except Exception as e:
                print(f"WARNING: Hotel photo download failed: {e} — skipping hotel photo in PDF")

        # Build the markdown file in tmpdir
        if map_markdown:
            # Insert a fresh map on the first generation, or replace an old
            # generated map when the user regenerates editable brochure text.
            if "<!-- RESTAURANT_MAP -->" in full_md:
                full_md = full_md.replace("<!-- RESTAURANT_MAP -->", map_markdown, 1)
            else:
                full_md = re.sub(
                    r"!\[\]\(<?map-restaurants\.png>?\)\s*\{\s*width\s*=\s*[^}]+\}",
                    map_markdown.strip(),
                    full_md,
                    count=1,
                )
        else:
            full_md = full_md.replace("<!-- RESTAURANT_MAP -->", "", 1)
            full_md = re.sub(
                r"!\[\]\(<?map-restaurants\.png>?\)\s*\{\s*width\s*=\s*[^}]+\}",
                "",
                full_md,
                count=1,
            )
        if hotel_image_path:
            if engine == "typst":
                hotel_markdown = _typst_image_block(
                    hotel_md_ref or hotel_image_path,
                    layout["hotel_image_width_percent"],
                    layout["hotel_image_alignment"],
                )
            else:
                hotel_markdown = (
                    f"\n\n![](<{hotel_md_ref or hotel_image_path}>)"
                    f"{{width={layout['hotel_image_width_percent']}%}}\n\n"
                )
            if "<!-- HOTEL_PHOTO -->" in full_md:
                full_md = full_md.replace("<!-- HOTEL_PHOTO -->", hotel_markdown, 1)
            else:
                # A previous generation stores a temporary `hotel.jpg/png`
                # reference in editable Markdown. Replace it with the new
                # image created for this render instead of letting Typst look
                # for a file from the already-deleted temp directory.
                full_md = re.sub(
                    r"!\[\]\(<(?:hotel|hotel_[^>]+)\.(?:jpe?g|png)>\)\s*\{\s*width\s*=\s*[^}]+\}",
                    hotel_markdown.strip(),
                    full_md,
                    count=1,
                    flags=re.IGNORECASE,
                )
        else:
            full_md = full_md.replace("<!-- HOTEL_PHOTO -->", "", 1)
            full_md = re.sub(
                r"!\[\]\(<(?:hotel|hotel_[^>]+)\.(?:jpe?g|png)>\)\s*\{\s*width\s*=\s*[^}]+\}",
                "",
                full_md,
                count=1,
                flags=re.IGNORECASE,
            )

        render_md = _prepare_markdown_for_engine(full_md, engine, layout)
        _ensure_no_layout_markers(render_md, "Pandoc input")
        md_file = os.path.join(tmpdir, "guide.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(render_md)
        # Return/save only clean, user-editable Markdown. Renderer layout is
        # inferred from the headings and restaurant-card content at render time.
        debug_md = os.path.join(guides_dir, f"guide_{safe_city}_{timestamp}.md")
        with open(debug_md, "w", encoding="utf-8") as f:
            f.write(_strip_layout_markers(full_md))

        extra_args = [
            "--standalone",
            f"--template={template_path}",
            "--toc",
            "--toc-depth=2",
            "--number-sections",
            "--wrap=none",
            f"--resource-path={tmpdir}",
        ]

        # Logo
        if os.path.exists(logo_path):
            # XeLaTeX cannot include this SVG reliably. Typst can use it directly.
            try:
                if engine == "typst":
                    logo_name = "logo.svg"
                    shutil.copy(logo_path, os.path.join(tmpdir, logo_name))
                    logo_dest = logo_name
                else:
                    import cairosvg
                    logo_png = os.path.join(tmpdir, "logo.png")
                    cairosvg.svg2png(url=logo_path, write_to=logo_png, output_width=128, output_height=128)
                    # Relative name: the .tex is compiled inside this folder.
                    logo_dest = os.path.basename(logo_png)
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
                # Relative name: the source is compiled inside this folder.
                cover_dest = os.path.basename(img_dest)
                extra_args.append(f"--variable=cover-image:{cover_dest}")

        # Write the editable source (brochure.typ / brochure.tex) into the
        # persistent folder, then compile it. The user can edit this file by
        # hand and rebuild it later with rebuild_from_source().
        try:
            if engine == "xelatex":
                source_file = os.path.join(tmpdir, "brochure.tex")
                pypandoc.convert_file(
                    md_file, "latex", format="markdown",
                    outputfile=source_file, extra_args=extra_args,
                )
                _compile_latex(source_file, output_pdf)
            else:
                source_file = os.path.join(tmpdir, "brochure.typ")
                typst_args = [
                    *extra_args,
                    f"--lua-filter={_typst_layout_filter_path()}",
                ]
                pypandoc.convert_file(
                    md_file, "typst", format="markdown",
                    outputfile=source_file, extra_args=typst_args,
                )
                _ensure_no_layout_markers(
                    Path(source_file).read_text(encoding="utf-8"), "generated Typst source"
                )
                _compile_typst(source_file, output_pdf, tmpdir)
        except Exception as e:
            print(f"PDF conversion failed for {md_file} using {engine}: {e}")
            raise

    return output_pdf, _strip_layout_markers(full_md)


def current_engine() -> str:
    """Expose the active renderer for the API/UI without duplicating config access."""
    return config.PDF_ENGINE


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


def _legend_cuisines(restaurant_data: list[dict] | None) -> list[str]:
    """Cuisines to show in the map legend, in CUISINE_COLORS order.

    Only cuisines that actually appear on the map are listed, so the legend
    always matches the user's cuisine selection. Falls back to every known
    cuisine when no restaurant data is available.
    """
    colors = restaurants_svc.CUISINE_COLORS
    present = {r.get("cuisine") for r in (restaurant_data or [])}
    chosen = [c for c in colors if c in present]
    return chosen or list(colors)


def _build_map_markdown(
    map_path: str,
    engine: str,
    width_percent: int,
    cuisines: list[str] | None = None,
) -> str:
    """Build renderer-specific restaurant map markup with a cuisine legend."""
    map_file = Path(map_path).name
    colors = restaurants_svc.CUISINE_COLORS
    cuisines = cuisines or list(colors)
    per_row = 3
    rows = [cuisines[i:i + per_row] for i in range(0, len(cuisines), per_row)]
    if engine == "typst":
        legend_rows = [
            "   ".join(
                f'#text(fill: rgb("{colors[c]}"))[●] {c}' for c in row
            )
            for row in rows
        ]
        return (
            "\n\n```{=typst}\n"
            "#align(center)[\n"
            f"  #image(\"{map_file}\", width: {width_percent}%)\n"
            "  #v(6pt)\n"
            "  #text(size: 8pt)["
            + "\\\n".join(legend_rows)
            + "]\n]\n```\n"
        )
    tabular_rows = []
    for row in rows:
        cells = [
            f"\\textcolor[HTML]{{{colors[c].lstrip('#')}}}"
            f"{{\\large\\textbullet}} {c}"
            for c in row
        ]
        cells += [""] * (per_row - len(cells))
        tabular_rows.append(" &\n".join(cells))
    legend = (
        "\\begin{center}\n"
        "\\begin{tabular}{ll@{\\hspace{12pt}}ll@{\\hspace{12pt}}ll}\n"
        "\\textbf{Cuisine} & & &  \\\\[2pt]\n"
        "\n"
        + " \\\\\n\n".join(tabular_rows)
        + "\\\\\n"
        "\\end{tabular}\n"
        "\\end{center}\n"
    )
    return (
        "\n\n![](" + map_file + "){ width=100% }\n\n"
        + legend
    )


def _prepare_markdown_for_engine(markdown_text: str, engine: str, layout: dict) -> str:
    """Build private renderer markup from clean user-facing brochure Markdown."""
    source = _strip_layout_markers(markdown_text)
    # Page-break directives are visible in CodeMirror but hidden by Markdown
    # previews. Accept legacy \newpage lines from earlier brochures too.
    source = re.sub(r"<!--\s*pagebreak\s*-->", "{{PAGE_BREAK}}", source, flags=re.IGNORECASE)
    source = source.replace("\\newpage", "{{PAGE_BREAK}}")
    if engine == "xelatex":
        return source.replace("{{PAGE_BREAK}}", "\\newpage")

    typst_markdown = source.replace("{{PAGE_BREAK}}", "::: {.page-break}\n:::")
    # Old editable brochure markdown may contain the XeLaTeX-only map legend
    # generated before Typst support. The Typst map renderer supplies its own
    # legend, so discard that incompatible raw LaTeX block.
    typst_markdown = re.sub(
        r"\\begin\{center\}\s*\\begin\{tabular\}.*?\\end\{tabular\}\s*\\end\{center\}\s*",
        "",
        typst_markdown,
        flags=re.DOTALL,
    )
    heading_gap = layout["restaurant_heading_gap_pt"]
    typst_markdown = re.sub(
        r"(?m)^(## .+ Restaurants\s*$)",
        lambda match: (
            f"{match.group(1)}\n\n```{{=typst}}\n#v({heading_gap}pt)\n```"
        ),
        typst_markdown,
    )
    if layout["keep_restaurant_cards_together"]:
        typst_markdown = _wrap_restaurant_cards_for_typst(
            typst_markdown, layout["restaurant_card_gap_pt"]
        )
    return typst_markdown


def _add_brochure_restaurant_pagebreaks(markdown_text: str) -> str:
    """Add default editable page breaks only to brochure Markdown.

    Restaurant-search results are also displayed in the Restaurants tab, so
    they remain free of PDF directives. This function is called only while the
    brochure document is assembled.
    """
    if not markdown_text:
        return ""
    clean = re.sub(
        r"(?im)^\s*(?:<!--\s*pagebreak\s*-->|\\newpage)\s*$\n?",
        "",
        markdown_text,
    )
    return re.sub(
        r"(?m)^(## .+ Restaurants\s*$)",
        "<!-- pagebreak -->\n\n\\1",
        clean,
    )


def _wrap_restaurant_cards_for_typst(markdown_text: str, gap_pt: int) -> str:
    """Wrap restaurant cards without relying on fragile multiline regexes."""
    output: list[str] = []
    card_lines: list[str] | None = None

    for line in markdown_text.splitlines():
        is_card_title = bool(re.match(r"^\*\*[^\n]+\*\* \([^)]+\)\s*$", line))
        next_section = (
            line.startswith("## ")
            or line.startswith("# ")
            or line.startswith("::: {.page-break}")
        )
        if card_lines is not None and (is_card_title or next_section):
            output.append("::: {.restaurant-card}")
            output.extend(card_lines)
            output.append(":::")
            output.extend(["```{=typst}", f"#v({gap_pt}pt)", "```"])
            card_lines = None

        if card_lines is None and is_card_title:
            card_lines = [line]
            continue

        if card_lines is not None:
            card_lines.append(line)
            continue

        output.append(line)

    # Finish the final restaurant card at end of document. Incomplete/manual
    # edits are still preserved as normal card content.
    if card_lines is not None:
        output.append("::: {.restaurant-card}")
        output.extend(card_lines)
        output.append(":::")

    return "\n".join(output)


def _strip_layout_markers(markdown_text: str) -> str:
    """Remove internal layout control markers from human-readable debug output."""
    return re.sub(
        r"<!--\s*(?:PAGE_BREAK|RESTAURANT_CARD_START|RESTAURANT_CARD_END)\s*-->\s*",
        "",
        markdown_text,
    )


def _ensure_no_layout_markers(text: str, stage: str) -> None:
    """Prevent internal layout controls from ever appearing in a generated PDF."""
    if re.search(r"RESTAURANT_CARD_(?:START|END)|PAGE_BREAK", text):
        raise RuntimeError(f"Internal layout markers leaked into {stage}")


def _typst_image_block(path: str, width_percent: int, alignment: str) -> str:
    """Return raw Typst markup for a controlled hotel-image layout."""
    safe_path = path.replace('"', "")
    return (
        "\n\n```{=typst}\n"
        f"#align({alignment})[#image(\"{safe_path}\", width: {width_percent}%)]\n"
        "```\n\n"
    )


def _typst_layout_filter_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "filters", "typst_layout.lua")


def _typst_command() -> str:
    """Locate Typst, including winget's install location before PATH refresh."""
    configured = config.TYPST_COMMAND
    if os.path.isabs(configured) and os.path.exists(configured):
        return configured
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    winget_root = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"
    )
    if winget_root and os.path.exists(winget_root):
        matches = list(Path(winget_root).glob("Typst.Typst_*/*/typst.exe"))
        if matches:
            return str(matches[0])
    raise FileNotFoundError(
        "Typst executable was not found. Install Typst or set TYPST_COMMAND to its executable path."
    )


def _compile_typst(typst_file: str, output_pdf: str, root_dir: str) -> None:
    """Compile Pandoc-generated Typst using the local Typst CLI."""
    result = subprocess.run(
        [_typst_command(), "compile", typst_file, output_pdf, "--root", root_dir],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Typst compilation failed: {details}")


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
