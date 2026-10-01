# Trip Planner — Development Context

Session-to-session state tracking, known issues, and development notes.

---

## Project Location

`/home/dbr6208/projects/myTrip_Planner/`

## Running Servers

| Server    | Command                                      | URL                          |
|-----------|----------------------------------------------|------------------------------|
| Backend   | `uvicorn backend.main:app --reload --port 8000` | http://localhost:8000     |
| Frontend  | `npx vite --host 0.0.0.0 --port 5173`          | http://localhost:5173     |

## Environment (`.env`)

| Key                    | Source        | Purpose                         |
|------------------------|---------------|---------------------------------|
| `OPENROUTER_API_KEY`   | OpenRouter    | Main LLM provider                |
| `OPENROUTER_LAYOUT_MODEL` | OpenRouter | Constrained brochure layout chat (defaults to `openai/gpt-6-luna`) |
| `TAVILY_API_KEY`       | Tavily        | Web search + cover image search |
| `ORS_API_KEY`          | OpenRouteService | Routing & distance matrix    |
| `GOOGLE_MAPS_API_KEY`  | Google        | Places API (hotels, restaurants)|
| `PDF_ENGINE`           | Local config  | `xelatex` default; set `typst` to evaluate Typst output |
| `TYPST_COMMAND`        | Local config  | Optional path/name of Typst executable |

## Branches

- `main` — active development
- `feature/typst-pdf-hitl` — Typst renderer and brochure-layout work
- `origin/modernization/phase-0-baseline` — legacy reference

## Git Remotes

- `origin` → `https://github.com/DBR6208/trip-planner.git`

## Known Issues / Remaining Work

1. **Restaurant map screenshot reliability** — Playwright Chromium can fail if tiles don't load. Folium's `_to_png()` is a potential alternative.
2. **Temp cleanup on API error** — if PDF generation succeeds but finalize fails, `guides/temp/` isn't cleaned automatically.
3. **Cover image quality** — content-type filtering tightened to JPEG/PNG only, but people/animal images can still slip through if the URL doesn't contain keyword clues. No vision-based filtering.
4. **Typst visual parity** — Typst is functional and opt-in, but should continue to be visually compared with the established XeLaTeX output before becoming the default renderer.

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
- Layout chat uses constrained GPT Luna tool calls for spacing, card splitting, and image layout; page breaks remain manual in Markdown

## PDF Notes

- Format: JPEG/PNG only for cover images and map screenshots
- Restaurant map: Markdown image syntax with hyphenated filenames (Pandoc-safe)
- Hotel photo: embedded at 45% width
- Cover image: 70% title page width
- Compressed via Ghostscript (optional, non-blocking)
- LaTeX template uses `\detokenize{}` for image paths with underscores
- Legend uses `\faUtensils` colored bullets per cuisine
- PDF engine: `PDF_ENGINE=xelatex` is the immediate rollback; `PDF_ENGINE=typst` uses `travel_template.typ` and `filters/typst_layout.lua`

## Config Quick Reference (`backend/config.py`)

- `HOME_ADDRESS` = `Heirweg 85A, 9190 Stekene, Belgium`
- `ALLOWED_CUISINES` = Local, Italian, Croatian, Grill, Steakhouse, Seafood
- `RESTAURANT_SEARCH_RADIUS` = 3000
- `WALK_DISTANCE_MAX_METERS` = 2500 (straight-line cap; taxi is acceptable)
- `REVIEW_MINIMUM` = 50 | `REVIEW_MINIMUM_HIGH_RATING` = 100
- `BATTERY_CAPACITY_KWH` = 78.0 | `CONSUMPTION_KWH_PER_100KM` = 17.31
- `PREFERRED_CHARGING_BRANDS` = Circle K, Fastned, Ionity, BP, Shell, EnBW, E.ON, Allego

## Recent Milestones

- **2026-09-17**: README refresh, PDF image hardening (JPEG/PNG only, path detokenize), LLM fallback widened for DNS/reset errors
- **2026-09-14**: COOP fix (maps switched to `dangerouslySetInnerHTML`), PDF temp/cleanup workflow, legend formatting
- **2026-09-12**: Cover image overhaul + CodeMirror editor + PDF.js preview
- **2026-09-11**: BFS route planner replaces greedy algorithm
- **2026-09-02**: All 15 REQUIREMENTS.md issues resolved
- **2026-10-01**: Added opt-in Typst renderer with XeLaTeX rollback, fit-to-width PDF preview, constrained GPT Luna layout controls, manual hidden brochure page-break directives, broader restaurant radius, and stronger cuisine/name cleanup.

## File Structure (relevant files)

```
backend/
├── main.py                     FastAPI endpoints, including brochure layout chat
├── config.py                   API keys, renderer selection, thresholds, routes, constants
├── services/
│   ├── llm.py                  LLM prompt orchestration + fallback
│   ├── city_guide.py           Tavily + LLM city description
│   ├── hotels.py               Google Places + Folium map + parking
│   ├── restaurants.py          Cuisine filter + walking cap + format
│   ├── tourist_office.py       Tourist info lookup
│   ├── geo.py                  Geocoding + ORS + Google Maps URLs
│   ├── charging.py             BFS route planner + ORS distance matrix
│   ├── planner.py              Weekend itinerary prompts
│   ├── pdf.py                  Markdown → Pandoc → XeLaTeX or Typst PDF
│   ├── layout_chat.py          GPT Luna constrained layout-setting interpreter
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
        ├── PDFPreview.tsx      Fit-to-width EmbedPDF viewer
        └── HtmlPreview.tsx     Rendered markdown
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