# Brochure Status

This file tracks what has been covered in the brochure/PDF workflow and what still needs attention.

## Covered

- PDF generation via pandoc + XeLaTeX with custom LaTeX template
- Hotel photo download and embedding at 45% width
- Restaurant map screenshots via Playwright (headless Chromium)
- Restaurant map shown at 100% width, no figure caption
- Cuisine legend below map as centered LaTeX table with colored bullets
- Ghostscript PDF compression (optional, failure doesn't block generation)
- EmbedPDF viewer for brochure preview (100% zoom, horizontal scroll)
- Cover image: Wikipedia article images + Tavily + tourist office website
- User upload/URL input for cover images
- CodeMirror editor (light theme) for brochure markdown editing
- PDFs saved to `guides/temp/` during generation, finalized to `guides/{city}.pdf` on download
- Temp directory cleaned on finalize

## Still Needs Attention

- **Restaurant map screenshot reliability** — Playwright Chromium can fail if tiles don't load. Consider Folium's `_to_png()` as alternative (see below)
- **guides/ temp cleanup on API error** — if finalize fails after generation, temp isn't cleaned
- **Image centering** — should be verified in the final PDF output for both hotel photo and restaurant map
- **PDF compression** — Ghostscript compression is optional; verify quality/size tradeoff

## Folium PNG Note

Folium has an internal PNG export helper that may be useful:

```python
def _to_png(
    self, delay: int = 3, driver: Any = None, size: Optional[Sequence[int]] = None
) -> bytes:
    """Export the HTML to byte representation of a PNG image.
    Uses selenium to render the HTML and record a PNG.
    Uses a headless Firefox webdriver by default.
    """
```

Suggested follow-up:
- Try using Folium's PNG export path for the restaurant map
- Increase render delay if tiles or markers are not fully loaded

## Directory Structure

```
guides/
├── temp/     # Generated PDFs (created on generation, cleaned on download)
├── Aachen.pdf    # Finalized brochures (created on download finalize)
├── Koeln.pdf
└── ...
```