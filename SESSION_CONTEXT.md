# Session Context — 2026-08-28

## Project
`/home/dbr6208/projects/myTrip_Planner/`

## Architecture (current)
- **Backend:** FastAPI (Python) on port 8000 — 11 API endpoints
  - `backend/main.py` — app entry point
  - `backend/config.py` — all constants (addresses, thresholds, limits)
  - `backend/templates/travel_template.tex` — LaTeX PDF template
  - `backend/services/` — 9 service modules (llm, city_guide, hotels, restaurants, tourist_office, geo, charging, planner, pdf)
  - `backend/requirements.txt` — pinned Python deps
- **Frontend:** React 19 + TypeScript 6 + Vite 8 + Tailwind 4
  - `frontend/src/App.tsx` — 6-step wizard (889 lines, single-page, react-markdown + remark-gfm)
  - `frontend/src/index.css` — DBG Travel brand theme (navy/gold, matches LaTeX PDF)
- **Original (frozen):** `myTripPlanner_V08.ipynb` — Gradio notebook, not updated
- **Brochures:** `brochures/` — 12 existing PDFs + recent test outputs

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

## Action points (next session priorities)

### A. Frontend CSS rework ⚡ DONE 2026-08-28
Complete rework completed:
- **react-markdown** (v10) + remark-gfm installed, replacing the regex `renderMarkdown()` hack and `dangerouslySetInnerHTML` — all 9 content areas now use proper GFM markdown rendering
- **CSS polish** — full DBG brand theme applied matching the LaTeX/PDF aesthetic:
  - Navy (`#003366`) section headings with gold (`#A07F40`) top/bottom borders — mirrors the PDF `travelblue`/`travelgold` scheme
  - Gold horizontal rules, gold blockquote left borders, gold tab active underline
  - Professional table styling with navy header + zebra striping
  - Subtle warm off-white background (`#f8f7f4`) matching the brand
  - Custom scrollbar styling
- **Error handling** — persistent dismissible error banner (removed 5s auto-dismiss timeout)
- **Mobile responsive** — collapsible sidebar via hamburger toggle on small screens (sidebarOpen state), sidebars hide/shown with a click
- **DaisyUI overrides** — custom brand colors, input/radio/checkbox/button focus states
- Production build passes cleanly (TypeScript + Vite)

### B. PDF layout judge LLM
The LaTeX template uses `nowidow` for widows/orphans but this needs **verification by a second AI model acting as a judge**. The judge LLM should:
- Render or inspect the generated PDF (or its LaTeX source) for widows/orphans
- Check heading hierarchy consistency (no ### skipping levels)
- Verify no emoji or italic slipped through
- Validate TOC depth and page-break logic
- Return structured pass/fail per criterion
- Block PDF delivery if layout fails

This should be a separate service/call in the PDF pipeline, using a different model than the content generator (better to catch each other's mistakes).

### C. Docker containerization
Package the application for easy deployment:
- **Dockerfile for backend** — Python image + FastAPI + uvicorn
- **Dockerfile for frontend** — Node build stage + nginx static serve (or Vite preview)
- **docker-compose.yml** — orchestrates both + exposes ports
- **.dockerignore** for each service
- Documentation in README on how to `docker compose up`

### D. Remaining REQUIREMENTS.md issues
- Issue 4 (route maps in PDF): investigate saving Folium HTML maps as PNG (headless browser via selenium/playwright or map screenshot tool) and embedding via `\includegraphics`
- Issue 10 (brochure size consistency): add post-generation validation that compares against a target range
- Issue 13 (typo "depating"): grep the new backend code to confirm it doesn't exist

### E. Future (not started)
- Move to GitHub repo
- End-to-end test run to validate all 15 issues with a real brochure generation

## Session discipline
- This file should be updated on a regular basis during a session — not just at the end. Each significant change (code edits, test results, decisions) gets recorded as it happens so the file always reflects the current state.
- Keep the quickref accurate: completed issues move from "open" to "done" immediately, new blockers get added, work-in-progress items are noted.
- Before closing a session, ensure the action points section is current so the next session can pick up without re-discovery.

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