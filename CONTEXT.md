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
| `OPENROUTER_API_KEY`   | OpenRouter    | LLM provider (GPT-4o-mini)      |
| `TAVILY_API_KEY`       | Tavily        | Web search + cover image search |
| `ORS_API_KEY`          | OpenRouteService | Routing & distance matrix    |
| `GOOGLE_MAPS_API_KEY`  | Google        | Places API (hotels, restaurants)|

## Branches

- `main` — active development
- `origin/modernization/phase-0-baseline` — legacy reference

## Git Remotes

- `origin` → `https://github.com/DBR6208/trip-planner.git`

## Known Issues / Remaining Work

1. **Restaurant map screenshot reliability** — Playwright Chromium can fail if tiles don't load. Folium's `_to_png()` is a potential alternative.
2. **Temp cleanup on API error** — if PDF generation succeeds but finalize fails, `guides/temp/` isn't cleaned automatically.
3. **Cover image quality** — content-type filtering tightened to JPEG/PNG only, but people/animal images can still slip through if the URL doesn't contain keyword clues. No vision-based filtering.

## Key Conventions

- Cover images: Wikipedia article images + Tavily search (include_images=True)
- Brochure editor: CodeMirror (light theme) for editing markdown
- PDF preview: EmbedPDF viewer (125% zoom, vertical scroll)
- Maps: `dangerouslySetInnerHTML` (not iframe — Firefox COOP fix)
- Image URL validation at backend level (HEAD requests)
- User-provided images go into gallery list first (click to select)
- Folium maps with BeautifyIcon circle markers, color-coded
- Native HTML radio/checkbox controls, not button-toggles
- Restaurant cuisines: each starts on a `\newpage` in the PDF

## PDF Notes

- Format: JPEG/PNG only for cover images and map screenshots
- Restaurant map: Markdown image syntax with hyphenated filenames (Pandoc-safe)
- Hotel photo: embedded at 45% width
- Cover image: 70% title page width
- Compressed via Ghostscript (optional, non-blocking)
- LaTeX template uses `\detokenize{}` for image paths with underscores
- Legend uses `\faUtensils` colored bullets per cuisine

## Config Quick Reference (`backend/config.py`)

- `HOME_ADDRESS` = `Heirweg 85A, 9190 Stekene, Belgium`
- `ALLOWED_CUISINES` = Local, Italian, Croatian, Grill, Steakhouse, Seafood
- `WALK_DISTANCE_MAX_METERS` = 1500
- `REVIEW_MINIMUM` = 50 | `REVIEW_MINIMUM_HIGH_RATING` = 100
- `BATTERY_CAPACITY_KWH` = 78.0 | `CONSUMPTION_KWH_PER_100KM` = 17.31
- `PREFERRED_CHARGING_BRANDS` = Circle K, Fastned, Ionity, BP, Shell, EnBW, E.ON, Allego

## Recent Milestones

- **2026-09-17**: README refresh, PDF image hardening (JPEG/PNG only, path detokenize), LLM fallback widened for DNS/reset errors
- **2026-09-14**: COOP fix (maps switched to `dangerouslySetInnerHTML`), PDF temp/cleanup workflow, legend formatting
- **2026-09-12**: Cover image overhaul + CodeMirror editor + PDF.js preview
- **2026-09-11**: BFS route planner replaces greedy algorithm
- **2026-09-02**: All 15 REQUIREMENTS.md issues resolved

## File Structure (relevant files)

```
backend/
├── main.py                    618 lines — 18 endpoints
├── config.py                   76 lines — all constants & env vars
├── services/
│   ├── llm.py                  LLM prompt orchestration + fallback
│   ├── city_guide.py           Tavily + LLM city description
│   ├── hotels.py               Google Places + Folium map + parking
│   ├── restaurants.py          Cuisine filter + walking cap + format
│   ├── tourist_office.py       Tourist info lookup
│   ├── geo.py                  Geocoding + ORS + Google Maps URLs
│   ├── charging.py             BFS route planner + ORS distance matrix
│   ├── planner.py              Weekend itinerary prompts
│   ├── pdf.py                  Markdown → pandoc → PDF
│   └── cover_images.py         Wikipedia/Tavily/Bing image search
├── templates/
│   └── travel_template.tex     LaTeX brochure template
frontend/
└── src/
    ├── App.tsx                 6-tab wizard
    ├── api/client.ts           Backend API client
    ├── types/api.ts            TypeScript types
    └── components/
        ├── MarkdownEditor.tsx  CodeMirror
        ├── PDFPreview.tsx      EmbedPDF viewer
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