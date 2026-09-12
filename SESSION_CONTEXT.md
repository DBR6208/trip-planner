# Session Context: myTrip_Planner — Cover Image Overhaul (Tavily + User Upload)

**Session Date:** 2026-09-12  
**Status:** Cover image sources replaced: Wikipedia filter improved, Tavily replaces Commons/Bing, user upload/URL input added

---

## ✅ Fixed This Session (2026-09-12)

### Cover Image Source Overhaul

**Problem:** Bing Image Search and Wikimedia Commons text search returned images with people/animals — URL-level keyword filters couldn't catch them (e.g. Osnabrück Wikipedia article had 0/5 usable images, all portraits). The Commons API also rate-limits aggressively (403 after a few queries).

**Solution — three changes:**

1. **Wikipedia article image filter expanded** — added `_PORTRAIT_PATTERNS` list catching filename patterns like `crop`, `bundesarchiv`, `bild`, `stolperstein`, `retrato`, `hochformat`, `selfie`, `headshot`, etc. These patterns are checked in addition to the existing skip list.

2. **Bing Image Search and Wikimedia Commons text search removed** — both replaced by `_search_tavily_images()` which uses Tavily `search()` with `include_images=True`. Tavily returns direct image URLs from indexed photo sites (Unsplash, Pexels, Pixabay, Flickr, Wikimedia). Tavily was already configured and used elsewhere in the app.

3. **PDF fallback updated** — `_fetch_city_cover_image()` in pdf.py now uses Tavily instead of the broken Commons text search.

### Human-in-the-Loop: Custom Cover Image Input

**Added two ways for users to provide their own cover image:**

1. **URL input field** — paste any image URL directly
2. **File upload** — upload JPEG/PNG/GIF/WebP from local machine

Both set add the image to the gallery so the user clicks it to select.

**Backend:**
- New endpoint `POST /api/cover-images/upload` — accepts multipart file, returns CoverImageInfo
- New endpoint `POST /api/cover-images/from-url` — downloads URL server-side, saves, returns CoverImageInfo
- New endpoint `GET /api/pdf/cover/{filename}` — serves uploaded images

**Frontend:**
- Text input + "Set" button for URL, File input for upload
- Both add to the gallery (coverImages list), user clicks to select

### Brochure Editor with Side-by-Side PDF Preview

**Problem:** The old PDF flow was: select cover → Generate PDF → iframe preview (unreliable). No way to edit the markdown before compilation.

**Solution — four changes:**

1. **New endpoint `POST /api/brochure/markdown`** — takes trip data, runs `build_markdown()` only (no pandoc), returns the markdown string instantly.

2. **PDF preview via PDF.js** — replaced the old base64 iframe approach with a proper PDF.js canvas renderer. The preview endpoint now serves the PDF as `FileResponse(media_type="application/pdf", Content-Disposition: inline)` instead of base64 data URL.

3. **Side-by-side layout** — when a PDF is generated, the output area switches to a 2-column grid: editor on the left, PDF.js preview on the right. User edits markdown, clicks "Regenerate PDF", and the preview updates immediately.

4. **Edits preserved across preview cycles** — the editor stays visible at all times. `brochureMarkdown` state is never cleared, so going back from preview to editor keeps all changes.

**Files modified:**
- `backend/main.py` — added `BrochureMarkdownRequest`, `POST /api/brochure/markdown`, changed preview endpoint to serve PDF inline
- `frontend/src/components/PDFPreview.tsx` — NEW: PDF.js canvas renderer with page nav
- `frontend/src/App.tsx` — added `showEditor`, `brochureMarkdown` state; side-by-side editor+preview layout; new handlers `handleShowEditor`, `handleBackToEditor`
- `frontend/src/api/client.ts` — added `brochureMarkdown()` API call
- `frontend/src/types/api.ts` — added `BrochureMarkdownReq` type
- `frontend` — added `pdfjs-dist` npm dependency

### Investigated Rejected Approaches

| Approach | Result |
|----------|--------|
| Overpass/OSM image query (Poi_imf.py) | **Rejected** — unreliable hosts (Flickr, Google Photos, S3, hotel sites), wrong subject matter (abstract sculptures, Stolpersteine) |
| Commons Category search | **Rejected** — Wikimedia rate-limits aggressively (403 errors), category name matching is fragile |
| Wikipedia article images | **Kept + improved** — works well for most cities, now with better portrait filtering |

**Files modified:**
- `backend/services/cover_images.py` — added `_PORTRAIT_PATTERNS`, replaced `_search_wikimedia`/`_search_bing_images` with `_search_tavily_images()`, updated imports
- `backend/services/pdf.py` — replaced `_fetch_city_cover_image()` Commons text search with Tavily-based fallback
- `backend/main.py` — added `POST /api/cover-images/upload` and `GET /api/pdf/cover/{filename}` endpoints
- `frontend/src/api/client.ts` — added `uploadCoverImage()` API call
- `frontend/src/App.tsx` — added custom URL input, file upload UI, handler functions, state fields

---

## Feature Status Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Route calculation | ✅ Fixed | BFS + ORS distance matrix with greedy fallback |
| Route tab standalone | ✅ Done | Works without hotel; auto-recalculates on address changes |
| Station addresses | ✅ Clean | ftfy fixes CP1252 mojibake |
| Maps URL format | ✅ Fixed | Direct place link, no api=1 redirect |
| Cover image search | ✅ Tavily-based | Wikipedia filtered + Tavily replaces Commons/Bing |
| User cover image upload | ✅ Added | URL input + file upload in brochure sidebar |
| Explore tab | ✅ Clean | City guide text only, no galleries |
| PDF generation | ✅ Working | Tavily fallback + inline PDF.js preview |
| Brochure editor | ✅ Basic | Textarea editor + side-by-side PDF.js preview, edits preserved |
| Brochure code editor | ⏳ TODO | Replace textarea with CodeMirror (syntax highlighting, line numbers) |

---

## Known Remaining Work (Carried Forward)

- **Replace textarea with CodeMirror** — The Gradio notebook (`myTripPlanner_V08.ipynb`) used `gr.Code(language="markdown")` which is a CodeMirror editor with syntax highlighting and line numbers. The current React app uses a plain `<textarea>`. Install `@codemirror/lang-markdown` and `@codemirror/view` and create a proper editor component. (Not done yet — user will test on Windows first)

---

## Testing Checklist

- [ ] Go to Brochure tab → click "Find Cover Images" → verify images are from Wikipedia + Tavily
- [ ] Verify no portrait/people photos in results (check Osnabrück specifically)
- [ ] Paste an image URL → click "Set" → verify it selects as cover image
- [ ] Upload an image file → verify it uploads and selects
- [ ] Generate PDF with custom/uploaded image → verify it appears on cover
- [ ] Backend: verify Tavily API key is configured in .env
- [ ] Verify the old Bing/Commons search code is completely removed

---

## Files Modified (Current Session)

```
backend/services/cover_images.py
  - Added _PORTRAIT_PATTERNS list (populated with filename patterns)
  - Updated fetch_cover_images() strategy (drop Commons/Bing, add Tavily)
  - Added _search_tavily_images() replacing _search_wikimedia() and _search_bing_images()
  - Added from .. import config, import tempfile

backend/services/pdf.py
  - Rewrote _fetch_city_cover_image() to use Tavily instead of Commons text search

backend/main.py
  - Added POST /api/cover-images/upload endpoint
  - Added GET /api/pdf/cover/{filename} endpoint

frontend/src/api/client.ts
  - Added uploadCoverImage() multipart upload function

frontend/src/App.tsx
  - Added coverImageCustomUrl, coverImageUploading to state
  - Added handleSetCustomUrl(), handleUploadFile() handlers
  - Added URL input + file upload UI in brochure sidebar
```

---

## Config & Environment

- **Backend:** FastAPI + Tavily API + OSRM routing + Google Hotels/Places
- **Frontend:** React + Vite + Tailwind + CodeMirror
- **PDF Generation:** pandoc + LaTeX + Ghostscript compression
- **Dev Servers:** `uvicorn backend.main:app --reload --port 8000` and `npx vite --host 0.0.0.0 --port 5173`