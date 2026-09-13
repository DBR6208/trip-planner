# Brochure Status

This file tracks what has been covered so far in the brochure/PDF workflow and what still needs attention.

## Covered

- Added the missing backend dependencies for PDF generation and image handling:
  - `ftfy`
  - `cairosvg`
  - `playwright`
- Switched the brochure PDF preview to an embedded in-app viewer using EmbedPDF.
- Added support for generating the brochure PDF from the backend.
- Added page breaks so the brochure sections start on new pages where requested.
- Added hotel photo and restaurant map handling in the PDF pipeline.
- Added a dedicated LaTeX template for the brochure PDF.
- Added a separate markdown image flow for the hotel photo and restaurant map.

## Still Not Working

- The preview is usable, but it should be made scrollable and verified in the UI.
- Centering the image is still not behaving consistently in the generated PDF.
- The restaurant map is still unreliable and needs another pass.
- The `guides` directory keeps too many generated files and needs a cleanup strategy so old PDFs, markdown debug files, and copied images do not accumulate forever.

## Folium PNG Note

Folium has an internal PNG export helper that may help with the restaurant map.

The relevant method is:

```python
def _to_png(
    self, delay: int = 3, driver: Any = None, size: Optional[Sequence[int]] = None
) -> bytes:
    """Export the HTML to byte representation of a PNG image.
    Uses selenium to render the HTML and record a PNG. You may need to
    adjust the `delay` time keyword argument if maps render without data or tiles.

    Uses a headless Firefox webdriver by default, though you can provide your own.

    Examples
    --------
    >>> m._to_png()
    >>> m._to_png(delay=10)  # Wait 10 seconds between render and snapshot.
    """
```

Suggested follow-up:

- Try using Folium's PNG export path for the restaurant map.
- Increase the render delay if tiles or markers are not fully loaded.

## Notes

- The hotel section currently uses plain markdown image syntax.
- The LaTeX template was adjusted to center body images, but that behavior still needs validation in the final PDF output.
- The restaurant map screenshot path is still the weakest part of the PDF build.
- If starting from a fresh clone or if `node_modules` is missing, run `npm install` in `frontend` so `@embedpdf/react-pdf-viewer` is installed. The dependency is already listed in `frontend/package.json`, so a separate manual package add should not be necessary unless the lockfile or modules are missing.
- The hotel image markdown now points to the downloaded local file used during PDF generation, not the original Google image URL with its key.
