# Session Context — 2026-08-28

## Project
`/home/dbr6208/projects/myTrip_Planner/`
GitHub: https://github.com/DBR6208/trip-planner (private)

## Architecture (current)
- **Backend:** FastAPI (Python) on port 8000 — 11 API endpoints
  - `backend/main.py` — app entry point
  - `backend/config.py` — all constants (addresses, thresholds, limits)
  - `backend/templates/travel_template.tex` — LaTeX PDF template
  - `backend/services/` — 9 service modules (llm, city_guide, hotels, restaurants, tourist_office, geo, charging, planner, pdf)
  - `backend/requirements.txt` — pinned Python deps
- **Frontend:** React 19 + TypeScript 6 + Vite 8 + Tailwind 4
  - `frontend/src/App.tsx` — 6-step wizard (971 lines, single-page, react-markdown + remark-gfm)
  - `frontend/src/index.css` — DBG Travel brand theme (navy/gold, matches LaTeX PDF)
- **LLM:** OpenRouter (openai/gpt-4o) — configurable via OPENROUTER_MODEL
- **Original (frozen):** `myTripPlanner_V08.ipynb` — Gradio notebook, not updated
- **Brochures:** `brochures/` — output directory for generated PDFs (gitignored)

## Implementation status (REQUIREMENTS.md issues)

| # | Issue | Status |
|---|-------|--------|
| 1 | Wining & Dining — no restaurant names | DONE — city_guide.py prompt enforces |
| 2 | Selectable restaurant categories (6 cuisines) | DONE — config + frontend toggle + cuisine keyword filter |
| 3 | Consistent format (DBG Travel style) | DONE — single LaTeX template |
| 3b | No ### headings | DONE — secnumdepth=2, tocdepth=2, code uses ## only |
| 4 | Journey leg table + station list + maps | PARTIAL — leg tables work, Folium maps not in PDF yet |
| 5 | Departure address: Heirweg 85A, Stekene | DONE — config.py HOME_ADDRESS set |
| 6 | Walking distance cap 1.5 km | DONE — WALK_DISTANCE_MAX_METERS = 1500 |
| 7 | Compact restaurant format | DONE — bold name + compact bullets |
| 8 | permanently_closed filter + bold names | DONE — Google Places field queried + filtered |
| 9 | Review count threshold (>=50) | DONE — REVIEW_MINIMUM = 50 |
| 10 | Brochure size consistency | PENDING — no minimum content enforcement yet |
| 11 | Tourist Office structured list | DONE — address/website/maps list format |
| 12 | Hotel: bold name + structured list + description | DONE — format_hotel() implemented |
| 13 | Typo "depating" → "departing" | PENDING — verify not in new code |
| 14 | Planner rewrite with actual weekend pattern | DONE — planner.py has full Friday/Saturday/Sunday pattern |
| 15 | Layout: TOC depth 2, no widows, no emoji, no italic | DONE — nowidow package, emoji strip, tocdepth=2 |

## Recent work (this session: 2026-08-28)

### GitHub setup
- Repo created: DBR6208/trip-planner (private)
- `gh` CLI authenticated via device flow
- `.gitignore` created (Python, venv, .env, brochures/, node_modules, dist)
- README.md written with full project docs, architecture, setup guide
- README fixed: OpenRouter API key shown as primary, tech stack corrected
- 66 files committed as initial commit + 3 follow-up pushes

### Frontend UI fixes
- **Grid breakpoints:** All tabs changed from `lg:grid-cols-*` (1024px) to `md:grid-cols-*` (768px) — two-column layout works on narrower screens
- **Tab spacing:** Increased gap (0.5rem), padding (0.6rem 1rem), removed duplicate CSS rule
- **Links open in new tab:** All 8 ReactMarkdown instances now pass `components={markdownComponents}` which renders `<a>` tags with `target="_blank" rel="noopener noreferrer"`
- **Hotel list items:**
  - Radio button sits beside hotel name in a `flex items-center gap-3` row (inline, not above)
  - Star rating renders as actual ★★★★★ characters (amber-colored), parsed from "5-star" text string
  - Rating and address indented at `ml-8` (2rem) under the name row
  - Increased spacing between items (`space-y-2`)

## Action points (next session priorities)

### A. PDF layout judge LLM
The LaTeX template uses `nowidow` for widows/orphans but needs verification by a second AI model acting as a judge. See REQUIREMENTS.md for full spec.

### B. Docker containerization
Package for deployment: Dockerfile (backend), Dockerfile (frontend), docker-compose.yml.

### C. Remaining REQUIREMENTS.md issues
- Issue 4 (route maps in PDF): headless browser screenshot of Folium HTML → PNG → `\includegraphics`
- Issue 10 (brochure size consistency): post-generation validation against a target range
- Issue 13 (typo "depating"): grep the backend code to confirm it doesn't exist

### D. Frontend improvements (based on this session)
- Add a loading skeleton for the hotel detail area while the LLM generates descriptions
- After hotel search, auto-select the first hotel if there's only one result
- Consider adding a "refresh hotels" button to re-search

### E. Future (not started)
- End-to-end test run to validate all 15 issues with a real brochure generation

## Session discipline
- This file should be updated mid-session after every significant change (code edits, test results, decisions)
- Keep the quickref accurate: completed issues move from "open" to "done" immediately
- Before closing a session, ensure the action points section is current

## Key details (user preferences)
- Start address: Heirweg 85A, 9190 Stekene, Belgium
- Arrival window: 5-6 PM Friday
- Breakfast: 9-11 AM
- Evening pattern: hotel bar drink → short walk/explore → dinner → nightcap + UNO
- Saturday departure from hotel: ~5 PM
- Sunday: breakfast, pack, walk, depart to arrive home 5-7 PM
- Taxi if walk >20 min or bad weather
- Budget: ~1500-2000 EUR for 3 people (hotel, dinner, drinks)
- 4-5 star hotels only (no 3-star)
- Preferred cuisines: local, Italian, Croatian, grill, steak, seafood
- Other cuisines (Turkish, Syrian, Asian, etc.) never appear
- Time-of-day blocks, not clock times
- No AI fluff, no italic, no emoji anywhere
- Bold limited to: section headings, hotel names, restaurant names, key numbers