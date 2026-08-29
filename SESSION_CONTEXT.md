# Session Context — 2026-08-29

## Project
`/home/dbr6208/projects/myTrip_Planner/`
GitHub: https://github.com/DBR6208/trip-planner (private)

## Architecture (current)
- **Backend:** FastAPI (Python) on port 8000 — 13 API endpoints
  - `backend/main.py` — app entry point
  - `backend/config.py` — all constants (addresses, thresholds, limits), model names
  - `backend/templates/travel_template.tex` — LaTeX PDF template
  - `backend/services/` — 9 service modules (llm, city_guide, hotels, restaurants, tourist_office, geo, charging, planner, pdf)
  - `backend/requirements.txt` — pinned Python deps
- **Frontend:** React 19 + TypeScript 6 + Vite 8 + Tailwind 4 (v4, CSS-based config via `@import "tailwindcss"`)
  - `frontend/vite.config.ts` — MUST include the `tailwindcss()` plugin (see Critical Fix)
  - `frontend/src/App.tsx` — 6-step wizard, single-page, react-markdown + remark-gfm
  - `frontend/src/index.css` — DBG Travel brand theme (navy/gold, matches LaTeX PDF) + custom component classes
- **LLM:** OpenRouter — default: `z-ai/glm-5.3-flash`, fallback: `openai/gpt-4o-mini` (auto on overload)
- **Original (frozen):** `myTripPlanner_V08.ipynb` — Gradio notebook, not updated
- **Brochures:** `brochures/` — output directory for generated PDFs (gitignored)

## ⚠️ CRITICAL FIX THIS SESSION — Tailwind was never compiling

**Symptom:** UI changes "did nothing" — no spacing, no indentation, no two-column layout, radio above name, stars as text. Multiple rounds of JSX edits produced zero visible change.

**Root cause:** `frontend/vite.config.ts` only registered `react()`, NOT `tailwindcss()`. In Tailwind v4, the `@tailwindcss/vite` plugin is what makes Vite scan `.tsx` files and emit utility classes. Without it, the CSS contained ONLY the hand-written rules from `index.css` — every utility class (`flex`, `gap-3`, `ml-8`, `w-[260px]`, `grid`, `md:`, etc.) was silently absent. `npm run build` "passed" because it was just bundling CSS with no utilities — a false success signal.

**Fix (commit aba5493):** Added `import tailwindcss from '@tailwindcss/vite'` and `tailwindcss()` to the `plugins` array. Compiled CSS jumped from 26 KB → 64 KB; all utilities now generate.

**Lessons (do NOT repeat):**
- `npm run build` passing does NOT prove Tailwind classes are present. Verify: `grep -o '\.flex-row[^}]*}' dist/assets/index-*.css`
- When UI changes have no effect, check the compiled CSS for the classes BEFORE editing more JSX.
- Tailwind v4 requires the Vite plugin; there is no `tailwind.config.js` / `@tailwind` directives here.
- A hard browser refresh (Ctrl+F5 / Cmd+Shift+R) is needed after structural CSS changes.

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
| 7 | Compact restaurant format | DONE — bold name + compact bullets + short LLM description |
| 8 | permanently_closed filter + bold names | DONE — Google Places field queried + filtered |
| 9 | Review count threshold (>=50) | DONE — REVIEW_MINIMUM = 50 |
| 10 | Brochure size consistency | PENDING — no minimum content enforcement yet |
| 11 | Tourist Office structured list | DONE — address/website/maps list format |
| 12 | Hotel: bold name + structured list + description | DONE — format_hotel() implemented |
| 13 | Typo "depating" → "departing" | PENDING — verify not in new code |
| 14 | Planner rewrite with actual weekend pattern | DONE — planner.py has full Friday/Saturday/Sunday pattern |
| 15 | Layout: TOC depth 2, no widows, no emoji, no italic | DONE — nowidow package, emoji strip, tocdepth=2 |

## Recent work (2026-08-28)

### GitHub setup
- Repo created: DBR6208/trip-planner (private); `gh` CLI authenticated via device flow
- `.gitignore` created (Python, venv, .env, brochures/, node_modules, dist)
- README.md written; fixed to show OPENROUTER_API_KEY as primary + corrected tech stack

### Frontend UI fixes (after Tailwind was enabled)
- **Links in new tab:** All 8 ReactMarkdown instances use `components={markdownComponents}` → `<a target="_blank" rel="noopener noreferrer">`
- **Tab spacing:** gap 0.5rem, padding 0.6rem 1rem, removed duplicate CSS rule
- **Hotel tab layout:** `flex flex-row` — sidebar `w-[260px]`, detail `flex-1 min-w-0` (always two columns, no responsive stacking)
- **Hotel list items:** radio beside name (`flex items-center gap-3`); star rating as ★★★★★ (amber), parsed from backend `star_rating: "5-star"` text; rating/address indented `ml-8`
- **Critical fix:** enabled Tailwind v4 Vite plugin (see warning block)

### Backend restaurant formatting
- **Only name bold (commit 0f44171):** changed `*Address:*`/`*Walk:*`/etc. (single-asterisk emphasis that rendered bold) to plain `- ...` bullets; name stays `**Name**`
- **Short LLM description (commit 69b2890):** each restaurant now gets a one-line description generated by `llm.generate` (max 25 words / 200 chars), placed under the bold name before the bullets. Prompt enforces no-fluff/no-emoji/no-prices. User confirmed: keep the LLM call (do not switch to generic).

## Recent work (2026-08-29)

### Tab bar & placeholder rework
- **Tabs renamed:** "Eateries" → "Restaurants", "Itinerary" → "Planning"
- **Added Brochure tab** (id: 5, FileText icon) — dedicated tab for PDF generation
- **Placeholder step flow** now matches tab bar exactly with all 6 Lucide icons
- **Footer:** changed to `© DBG Travel 2026`
- **LLM prompt:** removed "luxury" from city guide prompt — city now described as "relaxed"

### LLM model changes
- **Default model:** `z-ai/glm-5.3-flash` (cheaper, set in config.py)
- **Auto-fallback:** when the primary model is overloaded, rate-limited, returns empty, or times out, `llm.generate()` silently retries with `openai/gpt-4o-mini`
- **Fallback model constant** added to config.py as `FALLBACK_MODEL`
- **Hotel endpoint** now does real Tavily web search for hotel info instead of passing empty context

### Hotel tab — Folium map with hotel markers
- **`generate_hotel_map()`** in `backend/services/hotels.py` — Folium map centered on tourist office showing hotels as colored CircleMarkers (darkred = 5-star, orange = 4-star)
- **When no selection yet:** all hotels in color
- **When a hotel is selected:** chosen hotel stays colored, others turn medium-light grey (`#b0b0b0`)
- Map rendered at 600px in an iframe (no scroll) in the hotel tab output area
- **Hotel detail** now includes a 288×216px Google Places photo next to the description
- **Parking**: `_find_nearby_parking()` searches Google Places for indoor garages within 500m, sorts by distance, keeps top 5
- **Hotel description** now prompts LLM for: Overview, Cleanliness, Bars/Lounge, Restaurants, Parking (on-site) — and format_hotel appends the real garage list

### Tourist Office — Folium map
- **`generate_tourist_office_map()`** in `backend/services/tourist_office.py` — Folium map with green info-sign marker, popup with address/website/Google Maps
- Displayed at 600px in the Explore tab below the tourist office info

### Backend infrastructure
- **`generate_with_search()`** now handles empty search_context gracefully — skips the "WEB RESEARCH CONTEXT" block and tells the LLM to answer from what it knows
- **`hotel_svc._tavily_search_hotel()`** — new function that searches Tavily for hotel reviews/amenities with focus on cleanliness, bar, lounge, restaurant, parking
- **`hotel_svc._find_nearby_parking()`** — searches Google Places for parking garages near hotel coords, returns up to 5 closest

## Action points (next session priorities)

### A. Verify UI end-to-end (now that Tailwind works)
- After hard refresh, confirm: two-column hotel layout, radio beside name, amber stars, indentation
- Test full flow: explore city → search hotels → select → restaurants → route → planning → brochure → PDF
- Confirm Folium tourist office map renders in the Explore tab

### B. PDF layout judge LLM
LaTeX template uses `nowidow` but needs verification by a second AI model acting as judge. See REQUIREMENTS.md for full spec.

### C. Docker containerization
Dockerfile (backend), Dockerfile (frontend), docker-compose.yml.

### D. Remaining REQUIREMENTS.md issues
- Issue 4 (route maps in PDF): headless browser screenshot of Folium HTML → PNG → `\includegraphics`
- Issue 10 (brochure size consistency): post-generation validation against a target range
- Issue 13 (typo "depating"): grep backend code to confirm absent

### E. Frontend improvements (nice-to-have)
- Loading skeleton for hotel detail area while LLM generates
- Auto-select first hotel when only one result
- "Refresh hotels" button

### F. Future (not started)
- End-to-end test run validating all 15 issues with a real brochure generation

### G. Frontend LLM model selector
- Add a UI dropdown or radio group to let the user choose which LLM model generates the brochure (e.g. `z-ai/glm-5.3-flash`, `openai/gpt-4o`, etc.)
- Pass the selected model from the frontend to the backend API endpoints that call the LLM
- Default stays at the config-level `OPENROUTER_MODEL`; frontend selection overrides it per-generation

## Session discipline
- Update this file mid-session after every significant change (code edits, test results, decisions)
- Keep the quickref accurate: completed issues move from "open" to "done" immediately
- Before closing a session, ensure the action points section is current so the next session picks up without re-discovery

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