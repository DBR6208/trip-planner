# Session Context: myTrip_Planner — Current State

**Session Date:** 2026-09-14
**Status:** All REQUIREMENTS.md issues resolved. Local development servers running.

---

## ✅ All 15 REQUIREMENTS.md Issues Resolved

| # | Issue | Status | Implementation |
|---|-------|--------|---------------|
| 1 | Wining & Dining (no specific restaurants) | ✅ | City guide describes local food scene only, no restaurant names |
| 2 | Cuisine selector (6 cuisines only) | ✅ | `ALLOWED_CUISINES` + `EXCLUDED_CUISINE_KEYWORDS` in config.py |
| 3 | Consistent format (DBG Travel branding) | ✅ | README.md, PLAN.md document template style |
| 3b | No ### headings | ✅ | build_markdown() / planner prompt enforce ## only |
| 4 | Journey leg table format | ✅ | Leg tables in charging.py output (compact tables, no verbose desc) |
| 5 | Departure address (Heirweg 85A) | ✅ | `HOME_ADDRESS` in config.py |
| 6 | Walking cap 1500m | ✅ | `WALK_DISTANCE_MAX_METERS` in config.py + restaurants.py filter |
| 7 | Compact restaurant listings | ✅ | `**bold name**` + description + address/walk/rating bullets |
| 8 | permanently_closed + review threshold | ✅ | `_get_place_details()` + `REVIEW_MINIMUM=50` in restaurants.py |
| 9 | Tourist office structured format | ✅ | `format_tourist_office()` outputs address/website/maps list |
| 10 | Hotel formatting | ✅ | Bold name + list (address/website/maps) + description |
| 11 | Typo "depating" | ✅ | Fixed in source |
| 12 | Planner: real weekend pattern + time blocks | ✅ | Complete planner prompt rewrite in planner.py |
| 13 | LaTeX: tocdepth=2, nowidow, no emoji | ✅ | travel_template.tex + _emoji_strip() in pdf.py |
| 14 | Brochure size (Ghostscript compress) | ✅ | compress_pdf() in pdf.py |
| 15 | No emoji, no italic, no fluff | ✅ | _emoji_strip(), bold-only rule enforced |

## ✅ CodeMirror Editor — Done

The plain `<textarea>` was replaced with `@uiw/react-codemirror` (light theme):
- `frontend/src/components/MarkdownEditor.tsx`
- Added `@codemirror/lang-markdown`, `@uiw/react-codemirror` to package.json

## ✅ Recent Changes (2026-09-14)

### COOP Fix — Map Popups
- Replaced all sandboxed `<iframe>` maps (hotel, restaurant, tourist office) with `<div dangerouslySetInnerHTML={...}>`
- Fixes Firefox `NS_ERROR_DOM_COOP_FAILED` when clicking Google Maps links in popups

### PDF Formatting
- Restaurant map: no figure caption, 100% width, cuisine legend with colored bullets (centered LaTeX table)
- Hotel photo: 45% width
- Map screenshot wait reduced from 5s to 2s

### PDF Temp/Cleanup Workflow
- Generated PDFs now save to `guides/temp/` instead of directly to `guides/`
- `POST /api/pdf/finalize` endpoint: copies PDF from `guides/temp/` to `guides/{city}.pdf` and clears the temp directory
- Frontend download buttons call finalize before downloading
- Preview endpoint reads from both `guides/temp/` and `guides/`

### Error Handling
- `BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError` handled gracefully in PDF endpoint
- Ghostscript compression wrapped in its own try/except
- Light theme for CodeMirror editor

## 🏗️ Architecture

```
myTrip_Planner/
├── backend/
│   ├── main.py              # FastAPI app, 15+ endpoints
│   ├── config.py            # API keys, thresholds, dirs
│   ├── services/
│   │   ├── city_guide.py    # Tavily search + LLM city guide
│   │   ├── geo.py           # Geocoding, ORS routing, generate_maps_url
│   │   ├── hotels.py        # Google Places hotel search + Folium map
│   │   ├── restaurants.py   # Google Places + cuisine filter + Folium map
│   │   ├── charging.py      # EV charging station route planning
│   │   ├── planner.py       # Weekend itinerary LLM prompts
│   │   ├── pdf.py           # Markdown assembly + pandoc LaTeX PDF
│   │   ├── cover_images.py  # Wikipedia + Tavily + website scraping
│   │   ├── tourist_office.py # Tourist info + Folium map
│   │   └── llm.py           # LLM prompt orchestration
│   ├── templates/
│   │   └── travel_template.tex  # LaTeX template
│   └── data/
│       └── unique_locations.csv
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.tsx          # 6-tab wizard (Explore → Hotel → Restaurants → Route → Planning → Brochure)
│       ├── api/client.ts    # Backend API client
│       ├── components/
│       │   ├── MarkdownEditor.tsx  # CodeMirror (light theme)
│       │   ├── PDFPreview.tsx      # EmbedPDF viewer (100% zoom, horizontal scroll)
│       │   └── HtmlPreview.tsx     # Rendered markdown preview
│       └── types/api.ts     # TypeScript types
├── guides/                  # Finalized PDFs
│   └── temp/                # Generated PDFs (cleaned on download)
├── SESSION_CONTEXT.md
├── REQUIREMENTS.md
├── BROCHURE_STATUS.md
├── PLAN.md
├── TEST_PLAN.md
└── README.md
```

## 🔧 Known Remaining Work

- **guides/ temp cleanup on frontend error** — if PDF generation succeeds but the finalize call fails, the temp dir isn't cleaned automatically
- **Restaurant map reliability** — Playwright Chromium screenshot can fail if map tiles don't load in time
- **Brochure editor light theme** — CodeMirror uses light theme (was dark, changed per user request)
- **The notebook** `myTripPlanner_V08.ipynb` is preserved as a frozen reference

## ⚙️ Running Servers

- Backend: `uvicorn backend.main:app --reload --port 8000` → http://localhost:8000
- Frontend: `npx vite --host 0.0.0.0 --port 5173` → http://localhost:5173