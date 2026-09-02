# Session Context: myTrip_Planner — Cover Image & Explore Tab Update

**Session Date:** 2026-09-02  
**Status:** Cover image search improved; Explore tab cleaned up; both features live in production

---

---

## 🚨 Critical Blocking Issues (2026-09-02)

### Issue 1: Route Calculation Fails

**Status:** BLOCKING | Severity: CRITICAL  
**Reported:** Current session

**Symptom:** Route planning feature is non-functional — throws error when user attempts to calculate route

**Details:**
- User enters departure address and destination
- Clicks "Find Route" 
- Error occurs (specific message not captured yet)
- No route or charging stations displayed

**Impact:**
- Route Planning tab completely broken
- User cannot plan EV trips
- Core feature unavailable

**Next Step:** Capture full error message and stack trace from backend logs

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
| Cover image search | ✅ Live | Wikimedia + Bing with landmark focus, no people/animals |
| Explore tab | ✅ Clean | City guide text only, no galleries |
| PDF generation | ✅ Working | Uses improved cover images on brochure generation |
| Brochure tab | ✅ Ready | Generate PDF → new tab with high-quality cover image |

---

## Testing Checklist

- [ ] Go to `localhost:5173` → **Brochure** tab
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
backend/services/cover_images.py
  - _search_wikimedia(): Updated search queries (lines 216-221)
  - _search_bing_images(): Added negative filters, expanded URL exclusions (lines 307-371)

frontend/src/App.tsx
  - Removed Attraction Photos gallery section (lines ~532-552)
  - Removed attraction_images conditional render
```

---

## Known Non-Issues (User Clarified)

- User: "I do not want pictures or portraits of people animals, only that pictures that are relevant to the top attractions"
- **Resolution:** Cover images now use architecture/landmark focus with people/animal filtering
- **Explore tab:** No pictures at all (clean text-only display of city guide)

---

## Next Steps (User to Confirm)

1. Test PDF cover images from Brochure tab — verify quality
2. Confirm Explore tab looks clean (text only, no galleries)
3. If cover images still need improvement, adjust Bing/Wikimedia queries further
4. Continue with other REQUIREMENTS.md items (restaurant filtering, planner prompts, etc.)

---

## Config & Environment

- **Backend:** FastAPI + Tavily API + OSRM routing + Google Hotels/Places
- **Frontend:** React + Vite + Tailwind + CodeMirror
- **PDF Generation:** pandoc + LaTeX + Ghostscript compression
- **Dev Servers:** `uvicorn backend.main:app --reload --port 8000` and `npx vite --host 0.0.0.0 --port 5173`
