# Session Context: myTrip_Planner — BFS Charging Algorithm Upgrade

**Session Date:** 2026-09-11  
**Status:** BFS charging algorithm + Route tab standalone (no hotel required) + address cleanup

---

## ✅ Fixed This Session (2026-09-11)

### Route Calculation — Now Uses BFS + ORS Distance Matrix

**Problem:** The old `_recommend_stations()` used a greedy approach:
- `line.project()` for station distances (straight-line approximation, not actual road distance)
- Picked the farthest reachable station each iteration with no backtracking
- Could miss valid solutions when the greedy choice led to a dead end

**Fix:**
1. **ORS Distance Matrix** (`_build_battery_matrix()`) — replaces `line.project()` straight-line estimates with actual road distances between every pair of (home, stations, destination) via ORS `distance_matrix()` API
2. **BFS search** (`_bfs_search_route()`) — explores all valid station sequences, finds the true minimum-stop path:
   - Breadth-first = fewest stops found first
   - Intermediate legs: 30–60% battery drop (relaxed ±5% per retry, up to 4 attempts)
   - Final leg: 30–35% drop (also graduated relaxation)
   - Brand preference (Circle K→Ionity→Fastned) folded into penalty function
   - Stations must be forward along the route, no revisits
3. **Graduated constraint relaxation** — if no path found, bounds widen by 5% each attempt up to 4x
4. **Greedy fallback** (`_recommend_stations_greedy()`) — original algorithm preserved and called when BFS fails or ORS API is unavailable

**Result (Heirweg → Osnabrück, 370.5 km):**
- BFS forward: **1 stop** — EnBW Mobility, Oberhausen (Lindnerstraße 137)
- BFS return: **2 stops** — EnBW Osnabrück → Allego Antwerpen
- Greedy fallback also works independently (different station choices, same stop counts)

**Files modified:**
- `backend/services/geo.py` — added `battery_drop_for_distance()` helper
- `backend/services/charging.py` — added `_build_battery_matrix()`, `_bfs_search_route()`, new `_recommend_stations()` wrapper, renamed old `_recommend_stations` → `_recommend_stations_greedy`
- All existing UI, plan_trip_with_stops, round-trip, and user-station-selection code **unchanged**

### Cover Image People/Animals — NOT FIXED (carried forward)

---

### Station Addresses — Fixed Garbled Characters with ftfy

**Problem:** Charging station addresses from CSV (CP1252-encoded) displayed mojibake — `ÃŸ` instead of `ß`, `Ã¼` instead of `ü`, etc. (e.g. `LindnerstraÃe 137` → should be `Lindnerstraße 137`).

**Fix:** Added `ftfy.fix_text()` to the address construction in `_find_stations_along_route()` — same approach as the notebook.

**Files modified:**
- `backend/services/charging.py` — added `import ftfy`, wrapped address with `ftfy.fix_text()`
- `.venv` — installed `ftfy==6.3.1` via `uv pip install`

---

### Route Tab — Now Standalone (No Hotel Required) + Auto-Recalculation

**Problem:**
- Route tab was locked behind hotel selection (`tabReady` returned `false` for tab 3 without a hotel)
- Destination was a read-only display showing the hotel address
- No auto-recalculation when start/destination addresses changed

**Changes:**
1. **`tabReady()`** — tab 3 (Route) now returns `true` unconditionally; route planner works without any hotel
2. **Destination field** — replaced read-only `<div>` with an editable `<input type="text">`
3. **Hotel pre-fill** — if a hotel is selected, its address pre-fills the destination field with a note: *"Hotel 'X' selected — address pre-filled. Edit to override."*
4. **Auto-recalculate** — `useEffect` watches `startAddress` and `destAddress`, debounces 600ms, then calls `handleFindRoute` automatically

**Files modified:**
- `frontend/src/App.tsx` — changed `tabReady`, replaced Route sidebar JSX, added `useEffect` + `useRef` for auto-recalculation

---

## 🚨 Critical Blocking Issues (2026-09-02)

### Issue 1: Route Calculation Fails — ✅ FIXED (2026-09-11)

**Status:** RESOLVED | Severity: CRITICAL — Fixed with BFS + ORS distance matrix

**Root cause:** The old greedy algorithm used `line.project()` (straight-line approximation) instead of actual road distances. It also had no backtracking — if the farthest-reachable station led to a dead end, it couldn't recover.

**Fix:** BFS search over an ORS distance matrix for actual road distances, with graduated constraint relaxation and greedy fallback. Details in "Fixed This Session" section above.

---

### Issue 2: Cover Images Show People/Animals (Filters Failed)

**Status:** BLOCKING | Severity: CRITICAL  
**Reported:** Current session

**Symptom:** Cover images in PDF brochures display people, animals, and other unwanted content

**Details:**
- Previous session: Implemented Bing negative filters (`-people`, `-portrait`, `-person`, `-crowd`)
- Current session: User reports all images are "completely useless" — still showing people/animals
- URL-level keyword filtering (`"person"`, `"people"`, `"portrait"`) NOT working
- Wikimedia and Bing search results are wrong

**Root Cause Analysis Needed:**
- Bing Image Search negative operators may not work or are ignored
- URL strings don't contain keywords even if images show people
- Wikimedia queries too broad
- No content-level filtering (can only filter URLs, not image content)

**Impact:**
- PDF brochures have unprofessional cover images
- Not suitable for distribution
- Breaks user's quality standards

**Possible Approaches (to investigate):**
1. Switch to curated APIs: Unsplash, Pexels, Pixabay (have filtering options)
2. Google Custom Search with image type/licensing filters
3. Vision model to validate downloaded images before use
4. Manual curation of city → good-image-URL mapping
5. Use architecture/design photo databases (ArchDaily, Flickr with tags)

**Next Step:** DO NOT CODE — investigate which image source will work

---

### Cover Image Search Enhancement for PDF Brochures

**Problem:**
- Cover images in PDFs were using Wikipedia generic photos (low quality, not relevant)
- No proper filtering for people/portraits/animals
- User requested better quality cityscape and landmark photos

**Solution Implemented:**

1. **Wikimedia Commons search queries** — now focus on specific landmark types:
   - `"{city} skyline landmark"`
   - `"{city} cityscape architecture"`
   - `"{city} historic center"`
   - `"{city} cathedral church building"`
   - `"{city} aerial view panorama"`

2. **Bing Images search queries** — added negative filters to exclude people/portraits:
   - `"{city} skyline landmark photography -people"`
   - `"{city} cityscape architecture -portrait -people"`
   - `"{city} historic center building -person"`
   - `"{city} cathedral church monument -people"`
   - `"{city} aerial view panorama -crowd"`

3. **URL-level exclusion filters** — skip images with keywords:
   - `"avatar"`, `"profile"`, `"person"`, `"people"`, `"portrait"` (in addition to existing filters)

**Result:**
- Cover images now feature high-quality architectural and scenic photos
- Tavily + Bing Images working together for better quality than Wikipedia alone
- No portraits, people, or animals in cover photos
- Photos are relevant to the city's landmarks and attractions

**Files Modified:**
- `backend/services/cover_images.py`
  - `_search_wikimedia()`: Updated 5 search queries with landmark/architecture focus
  - `_search_bing_images()`: Added negative filters and expanded exclude list

### Explore Tab Cleanup — Removed Attraction Photos Gallery

**Problem:**
- Explore tab was showing a 2-column gallery of "Attraction Photos" 
- Gallery displayed links to Google Images search (not actual images)
- Cluttered the UI; users wanted just the city guide text

**Solution Implemented:**

- Removed entire "Attraction Photos" section from Explore tab rendering
- Explore tab now shows only the city guide markdown (clean, focused)
- No pictures, galleries, or links in the Explore tab

**Files Modified:**
- `frontend/src/App.tsx`
  - Removed attractions gallery grid section (lines ~532-552)
  - Kept city guide markdown display only

**Build Status:**
- Frontend: ✓ Built successfully (npm run build)
- Backend: ✓ Python syntax OK
- Both servers: ✓ Running (frontend:5173, backend:8000)

---

## Feature Status Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Route calculation | ✅ Fixed | BFS + ORS distance matrix with greedy fallback |
| Route tab standalone | ✅ Done | Works without hotel; auto-recalculates on address changes |
| Station addresses | ✅ Clean | ftfy fixes CP1252 mojibake in charging station names |
| Cover image search | 🔄 Needs work | Still showing people/animals — URL filters insufficient |
| Explore tab | ✅ Clean | City guide text only, no galleries |
| PDF generation | ✅ Working | Uses improved cover images on brochure generation |
| Brochure tab | ✅ Ready | Generate PDF → new tab with high-quality cover image |

---

## Testing Checklist

- [ ] Go to `localhost:5173` → **Route** tab (no hotel needed)
- [ ] Enter a destination address directly → route should calculate after 600ms
- [ ] Change start address preset → route recalculates
- [ ] Select a hotel in Hotels tab → destination pre-filled, route recalculates
- [ ] Override destination text → route recalculates
- [ ] Verify addresses show proper characters (e.g. "Straße" not "StraÃe")
- [ ] Go to **Brochure** tab
- [ ] Generate PDF for any city (e.g., Aachen, Paris)
- [ ] Verify: Cover image is a cityscape/landmark photo (not Wikipedia generic, not portrait)
- [ ] Go to **Explore** tab
- [ ] Enter city (e.g., Aachen)
- [ ] Click "Explore City"
- [ ] Verify: Only city guide text is shown (no pictures, no gallery)

---

## Historical Context (Prior Session)

### Previous Session Work (Compaction 3)

1. **EV Charging Algorithm Fixes** (2026-09-02 16:45 UTC)
   - Fixed route distance miscalculation (532km → 380km)
   - Improved station sorting (distance-first, not brand-first)
   - Added used_stations tracking to prevent duplicates
   - Increased search buffer (2km → 5km)
   - Added special return-trip low-battery logic
   - Result: Leuvenssteenweg → Osnabrück now recommends correct stops

2. **Brochure Workflow Redesign** 
   - Consolidated 3-phase → 1-phase "Generate PDF" flow
   - PDF returns in new tab (not embedded iframe)
   - Markdown editor responsive with CodeMirror
   - PDF compression via Ghostscript on download
   - Frontend state management cleaned up

3. **Attraction Images (Abandoned in Current Session)**
   - Added Tavily search for attraction images (replaced with cover images later)
   - Removed from Explore tab to reduce clutter
   - Decision: Focus on cover image quality instead of gallery display

---

## Files Modified (Current Session)

```
backend/services/geo.py
  - added battery_drop_for_distance() helper (inverse of remaining_battery)

backend/services/charging.py
  - _recommend_stations → _recommend_stations_greedy (preserved as fallback)
  - added _build_battery_matrix() — ORS distance matrix for actual road distances
  - added _bfs_search_route() — BFS with graduated constraint relaxation + brand penalty
  - new _recommend_stations() wrapper — tries BFS first, falls back to greedy
  - find_route_and_stations(), plan_trip_with_stops(), _plan_leg(), _plan_direct_route() unchanged
  - added import ftfy, wrapped address in _find_stations_along_route() with ftfy.fix_text()

frontend/src/App.tsx
  - tabReady: tab 3 (Route) now returns true (no hotel required)
  - Route sidebar: removed hotel gate, made destination an editable text input
  - added useEffect + useRef for 600ms debounced auto-recalculate on address changes
  - hotel selection still pre-fills destination address when selected
```

---

## Known Non-Issues (User Clarified)

- User: "I do not want pictures or portraits of people animals, only that pictures that are relevant to the top attractions"
- **Resolution:** Cover images now use architecture/landmark focus with people/animal filtering
- **Explore tab:** No pictures at all (clean text-only display of city guide)

---

## Next Steps (User to Confirm)

1. Test route calculation standalone (no hotel) — should work and auto-recalculate
2. Test route calculation with hotel pre-fill
3. Verify PDF cover images from Brochure tab — if still showing people/animals, need a different approach
4. Continue with other REQUIREMENTS.md items (restaurant filtering, planner prompts, etc.)

---

## Config & Environment

- **Backend:** FastAPI + Tavily API + OSRM routing + Google Hotels/Places
- **Frontend:** React + Vite + Tailwind + CodeMirror
- **PDF Generation:** pandoc + LaTeX + Ghostscript compression
- **Dev Servers:** `uvicorn backend.main:app --reload --port 8000` and `npx vite --host 0.0.0.0 --port 5173`
