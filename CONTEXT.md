# Trip Planner — Development Context

Session-to-session state tracking, known issues, and development notes.

---

## Running Servers

Run from the project root (activate `.venv` first).

| Server    | Command                                      | URL                          |
|-----------|----------------------------------------------|------------------------------|
| Backend   | `uvicorn backend.main:app --reload --port 8000` | http://localhost:8000     |
| Frontend  | `cd frontend; npm run dev`                      | http://localhost:5173     |

## Environment (`.env`)

| Key                    | Source        | Purpose                         |
|------------------------|---------------|---------------------------------|
| `OPENROUTER_API_KEY`   | OpenRouter    | Main LLM provider                |
| `OPENROUTER_MODEL`     | OpenRouter    | Content/curation model, full ID incl. provider prefix (default `openai/gpt-4o-mini`) |
| `TAVILY_API_KEY`       | Tavily        | Web search + cover image search |
| `ORS_API_KEY`          | OpenRouteService | Routing & distance matrix    |
| `GOOGLE_MAPS_API_KEY`  | Google        | Places API (hotels, restaurants)|
| `PDF_ENGINE`           | Local config  | `xelatex` default; set `typst` to evaluate Typst output |
| `TYPST_COMMAND`        | Local config  | Optional path/name of Typst executable |

## Branches

- `main` — the only branch (local and on GitHub). The Typst renderer work from `feature/typst-pdf-hitl` was merged into it and that branch was deleted on 2026-10-04.

## Git Remotes

- `origin` → `https://github.com/DBR6208/trip-planner.git`

## Known Issues / Remaining Work

1. **Restaurant map screenshot reliability** — Playwright Chromium can fail if tiles don't load. Folium's `_to_png()` is a potential alternative.
2. **Temp cleanup on API error** — if PDF generation succeeds but finalize fails, `guides/temp/` isn't cleaned automatically.
3. **Cover image quality** — content-type filtering tightened to JPEG/PNG only, but people/animal images can still slip through if the URL doesn't contain keyword clues. No vision-based filtering.
4. **Typst visual parity** — Typst is functional and opt-in, but should continue to be visually compared with the established XeLaTeX output before becoming the default renderer.
5. **Restaurant selection is LLM-decided** — the final list can differ slightly between runs. A full 8-cuisine search takes about a minute (3 Places pages per cuisine, enrichment, one large LLM call).
6. **Cuisine list lives in two places** — `CUISINE_COLORS` (`restaurants.py`) and `CUI_COLORS` (`frontend/src/App.tsx`). Keep them in sync; the sidebar menu and the PDF map legend are built from them.
7. **`KNOWN_CHAINS`** (`config.py`) is a starting list for DE/BE/FR/NL/UK; repeated brands in the search results are also detected automatically.
8. **Lint** — oxlint reports one pre-existing warning (`findRouteRef.current = ...` assigned during render in `App.tsx`).

## Key Conventions

- Cover images: Wikipedia article images + Tavily search (include_images=True)
- Brochure editor: CodeMirror (light theme) for editing markdown
- PDF preview: EmbedPDF viewer (fit-to-width, vertical scroll); sidebar owns final download
- Maps: `dangerouslySetInnerHTML` (not iframe — Firefox COOP fix)
- Image URL validation at backend level (HEAD requests)
- User-provided images go into gallery list first (click to select)
- Folium maps with BeautifyIcon circle markers, color-coded
- Native HTML radio/checkbox controls, not button-toggles
- Restaurant search output remains free of brochure-only directives
- Brochure page breaks use editable `<!-- pagebreak -->` comments; the renderer converts them to XeLaTeX or Typst page breaks
- Brochure layout values are fixed in `LAYOUT_SETTINGS` (`pdf.py`); there is no layout chat any more
- Every PDF build keeps `brochure.typ` / `brochure.tex` + images in `guides/source/{city}/` (previous version in `{city}_previous/`); `POST /api/pdf/rebuild` recompiles the hand-edited file
- Restaurant search needs at least one ticked cuisine (HTTP 400 otherwise); there is no "search all" fallback
- Restaurant pipeline: wide search → generic filters (chains, bars, excluded cuisines, rating, 2.5 km) → enrichment → one LLM pass that sets the real cuisine; empty cuisines are simply left out (see README "Restaurant Selection Pipeline")

## PDF Notes

- Format: JPEG/PNG only for cover images and map screenshots
- Restaurant map: Markdown image syntax with hyphenated filenames (Pandoc-safe)
- Hotel photo: embedded at 45% width
- Cover image: 70% title page width
- Compressed via Ghostscript (optional, non-blocking)
- Image paths in the source are relative to `guides/source/{city}/` (the file is compiled inside that folder)
- Map legend is generated from the cuisines present on the map, using `CUISINE_COLORS` (both engines)
- PDF engine: `PDF_ENGINE=xelatex` is the immediate rollback; `PDF_ENGINE=typst` uses `travel_template.typ` and `filters/typst_layout.lua`

## Config Quick Reference (`backend/config.py`)

- `HOME_ADDRESS` = `Heirweg 85A, 9190 Stekene, Belgium`
- Selectable cuisines = keys of `CUISINE_COLORS` in `restaurants.py`: Italian, German, Mediterranean, Seafood, Croatian, French, Steakhouse, Belgian
- `WALK_DISTANCE_MAX_METERS` = 2500 (straight-line cap used by the restaurant search; taxi is acceptable)
- `REVIEW_MINIMUM` = 50 (plus rating ≥ 4.1)
- `EXCLUDED_CUISINE_KEYWORDS` (Turkish, Greek, Asian, … incl. DE/FR/NL spellings) and `KNOWN_CHAINS`
- `BATTERY_CAPACITY_KWH` = 78.0 | `CONSUMPTION_KWH_PER_100KM` = 17.31
- `PREFERRED_CHARGING_BRANDS` = Circle K, Fastned, Ionity, BP, Shell, EnBW, E.ON, Allego

## Recent Milestones

- **2026-09-17**: README refresh, PDF image hardening (JPEG/PNG only, path detokenize), LLM fallback widened for DNS/reset errors
- **2026-09-14**: COOP fix (maps switched to `dangerouslySetInnerHTML`), PDF temp/cleanup workflow, legend formatting
- **2026-09-12**: Cover image overhaul + CodeMirror editor + PDF.js preview
- **2026-09-11**: BFS route planner replaces greedy algorithm
- **2026-09-02**: All 15 REQUIREMENTS.md issues resolved
- **2026-10-01**: Added opt-in Typst renderer with XeLaTeX rollback, fit-to-width PDF preview, manual hidden brochure page-break directives, broader restaurant radius, and stronger cuisine/name cleanup.
- **2026-10-04**: Restaurant selection rebuilt (wide search, chain/bar/excluded-cuisine filters, single LLM classification, 2.5 km, at least one cuisine required, 8 cuisines, Belgium + neighbours); layout chat removed; hand-editable `brochure.typ`/`.tex` with rebuild endpoint; PDF map legend follows the selection; code cleanup (unused files, imports, endpoint, npm packages; `hotels.py` page-token bug fixed). Removed files are kept in `work/` for review. The `feature/typst-pdf-hitl` branch was merged into `main` and deleted (local + GitHub).

## File Structure (relevant files)

```
backend/
├── main.py                     FastAPI endpoints
├── config.py                   API keys, renderer selection, thresholds, routes, constants
├── services/
│   ├── llm.py                  LLM prompt orchestration + fallback
│   ├── city_guide.py           Tavily + LLM city description
│   ├── hotels.py               Google Places + Folium map + parking
│   ├── restaurants.py          Wide search → filters → LLM cuisine classification, format, map
│   ├── tourist_office.py       Tourist info lookup
│   ├── geo.py                  Geocoding + ORS + Google Maps URLs
│   ├── charging.py             BFS route planner + ORS distance matrix
│   ├── planner.py              Weekend itinerary prompts
│   ├── pdf.py                  Markdown → Pandoc → brochure.typ/.tex → PDF (+ rebuild from source)
│   └── cover_images.py         Wikipedia/Tavily/Bing image search
├── templates/
│   ├── travel_template.tex     XeLaTeX brochure template (default/rollback)
│   └── travel_template.typ     Typst brochure template (opt-in)
├── filters/
│   └── typst_layout.lua        Pandoc layout div conversion for Typst
frontend/
└── src/
    ├── App.tsx                 6-tab wizard
    ├── api/client.ts           Backend API client
    ├── types/api.ts            TypeScript types
    └── components/
        ├── MarkdownEditor.tsx  CodeMirror
        └── PDFPreview.tsx      Fit-to-width EmbedPDF viewer
guides/source/{city}/           Generated brochure.typ / brochure.tex + images (hand-editable, gitignored)
work/                           Files removed during the 2026-10-04 cleanup, kept for review (safe to delete)
```

## Quick Start

```bash
# Backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```