# Trip Planner — Brochure Review & Requirements

Review date: 2026-08-23  
Updated: 2026-09-02 (Cover image search, Explore tab cleanup)  
Docs read: Aachen.pdf, Bielefeld.pdf, Boulogne-sur-Mer.pdf, Köln.pdf, Dortmund.pdf
(plus several other PDFs in brochures/ for context)

---

## ✅ Recently Fixed (2026-09-02)

### Cover Image Search Improvements

**What was done:**
- Improved Wikimedia search queries to focus on landmarks and architecture: `"skyline landmark"`, `"cityscape architecture"`, `"historic center"`, `"cathedral church building"`, `"aerial view panorama"`
- Enhanced Bing Images search with negative filters (`-people`, `-portrait`, `-person`, `-crowd`) to exclude portrait photography
- Added URL-level filters to exclude avatar, profile, person, people, portrait keywords
- Removed attraction photos gallery from Explore tab (cluttered the UI; users should see city guide only)

**Result:**
- Cover images in PDF brochures now feature high-quality cityscape and landmark photos
- No low-quality Wikipedia generic images
- No portraits of people or animals
- Tavily-powered search with proper landmark/architecture focus

**Files modified:**
- `backend/services/cover_images.py` — improved `_search_wikimedia()` and `_search_bing_images()` with better queries and filters
- `frontend/src/App.tsx` — removed attraction photos gallery from Explore tab

### Explore Tab Restoration

**What was done:**
- Removed the "Attraction Photos" gallery section that was displaying clicked-through links
- Explore tab now shows only the city guide markdown (clean, simple, focused)
- No pictures or galleries in the Explore tab

**Files modified:**
- `frontend/src/App.tsx` — removed attractions gallery rendering

---

## 🚨 Critical Issues (Blocking, 2026-09-02)

### Issue 1: Route Calculation Fails with Error — ✅ FIXED (2026-09-11)

**Status:** RESOLVED — Severity: Critical  **Fix date:** 2026-09-11

**Root Cause:** The old greedy `_recommend_stations()` used `line.project()` (straight-line approximation) instead of actual road distances. It had no backtracking — if the farthest-reachable station led to a dead end, it couldn't recover. The actual error was a silent failure: the greedy algorithm returned an empty list or wrong stations.

**Fix:** Replaced with BFS + ORS distance matrix:
- `_build_battery_matrix()` — actual road distances via ORS `distance_matrix()` API
- `_bfs_search_route()` — BFS over battery-drop graph with graduated constraint relaxation
- Brand preference (Circle K → Ionity → Fastned) folded into penalty function
- Greedy algorithm preserved as `_recommend_stations_greedy()` fallback
- Route tab now works standalone (no hotel required) with auto-recalculate

**Result (Heirweg → Osnabrück, 370.5 km):**
- Forward: 1 stop — EnBW Mobility, Oberhausen (Lindnerstraße 137)
- Return: 2 stops — EnBW Osnabrück → Allego Antwerpen

**Files changed:**
- `backend/services/geo.py` — added `battery_drop_for_distance()`
- `backend/services/charging.py` — added BFS functions, kept greedy as fallback
- `frontend/src/App.tsx` — Route tab no longer requires hotel, auto-recalculate added

---

### Issue 2: Cover Images Still Showing People/Animals (Filters Not Working)

**Status:** BLOCKING  
**Severity:** Critical  
**Reported:** 2026-09-02 (current session)

**Problem:**
- Cover images in PDF brochures are displaying people and animals
- Negative filters and URL keyword exclusions are NOT working
- Images are "completely useless" for cover photos — inappropriate for professional brochure
- Bing search and Wikimedia queries are returning wrong content

**Expected Behavior:**
- Cover images should show only cityscapes, landmarks, architecture
- No people, portraits, faces, animals, or creatures
- Photos relevant to the city's main attractions (cathedrals, skylines, historic centers)

**Actual Behavior:**
- Search results include tourist photos with people
- Search results include animal/nature photos
- URL filters not catching these images
- Negative operators in Bing query (`-people`, `-portrait`) not effective

**Root Cause Analysis Needed:**
1. **Bing Image Search:** Negative operators may not work as expected or Bing may ignore them
2. **URL filtering:** Keywords like "people", "portrait" may not appear in URL itself
3. **Wikimedia queries:** May not be specific enough (too broad, catching generic/wrong results)
4. **Image content:** Can't filter by visual content without ML/vision analysis

**Possible Solutions (TBD):**
- Switch to different image source (e.g., Unsplash API, Pexels API, Pixabay API with proper filtering)
- Use Google Custom Search API with strict image licensing/type filters
- Implement image recognition/filtering (requires vision model to analyze downloaded images)
- Manually curate a list of good cover image URLs per city
- Use a specialized architecture/landmark photo database (Architekture Magazine, ArchDaily, etc.)

**Files to Check:**
- `backend/services/cover_images.py` — Bing search implementation, URL filtering logic
- Verify actual URLs being returned from Bing
- Test Bing queries manually in browser to see what results come back
- Check if negative operators (`-people`, `-portrait`) work in Bing Image Search
- Verify which images are actually being downloaded and used

**Current Code Issues:**
- `_search_bing_images()`: Uses regex `r'"murl":"([^"]+\.(?:jpg|jpeg|png|webp))"'` to extract URLs
- URL filters check for: `["icon", "logo", "flag", "badge", "1x1", "avatar", "profile", "person", "people", "portrait"]`
- Bing queries: Include `-people`, `-portrait`, `-person`, `-crowd` negative operators
- **Problem:** URL string may not contain these keywords even if image shows people

**Action Required:**
- DO NOT START CODING YET
- Capture actual image URLs being returned from cover_images search
- Compare URLs against what's appearing in actual PDF brochures
- Test if Bing's negative operators actually work (manual browser test)
- Investigate alternative image sources with better quality control
- Consider using an image filtering API or ML model to validate images before use

---

## ✅ What works well — preserve these
- **Tone** is relaxed, elegant, and practical — matches the brief
- **EV route planning** is detailed and functional (battery %, leg distances, charger details)
- **Weekend itineraries** are well-paced: relaxed evenings, moderate days, no strenuous activities
- **Hotel recommendations** are specific and well-described

---

## ❌ Issues to fix

### 1. "Wining & Dining" section should not list specific restaurants

Currently the city guide's "Wining & Dining" section includes restaurant suggestions (e.g. "Restaurant Suggestions" sub-section with specific names). It should only describe the local food and drink scene broadly — local wines, beers, spirits, culinary traditions — without naming specific restaurants or listing them by category.

**Action:** Remove individual restaurant references from the "Wining & Dining" section in the city guide. Keep only:
- Local wines, beers, and spirits (what to try)
- Regional culinary traditions
- General food culture description (markets, food festivals, street food character)

### 2. Restaurant categories should be selectable per brochure

The full restaurant listings (with addresses, ratings, walk times, descriptions) should live in a dedicated "Restaurant selection" section. The user should be able to choose which cuisine categories are included per brochure from this set:

- Local / regional cuisine
- Italian
- Croatian
- Grill
- Steakhouse
- Seafood

Other cuisines (Turkish, Syrian, Asian, Chinese, Thai, etc.) should never appear.

**Action:** Add a configuration option per city (or globally) to select which restaurant categories to include. Filter the LLM output or the Tavily search queries based on this selection. Add a code-level filter as a safety net to strip out any restaurant whose description contains keywords like "turkish", "syrian", "asian", "halal", "chinese", "thai", "lebanese", etc.

### 3. Inconsistent format across brochures

Two distinct formats exist:
- **Old style** (Aachen, Bielefeld, Dortmund): markdown-only headings, "Proposal weekend activities", restaurants grouped by cuisine
- **New style** (Boulogne-sur-Mer, Köln): "Weekend Travel Guide" branding, "Generated by DBG Travel", numbered TOC with page references

**Action:** Re-generate old-style brochures using the new format. Settle on one template.

### 3b. No `###` (third-level) headings anywhere in the brochure

The older brochures use `###` for sub-sections like restaurant categories, tourist office, hotel. These should never appear. Use only `#` (title) and `##` (section headings). Subsections under a `##` heading should use bold text or bullet lists, not another heading level.

**Action:** Ensure the template and LLM prompt never produce `###` headings. Use bold text or list formatting for sub-structure.

### 4. Journey section: replace verbose leg text with a compact table

**Current behavior (lines 1161, 1170-1171, 1181-1187, 1230, 1239-1241, 1249-1255):**
- Each leg is written out as a `### Leg N:` subheading with distance and battery text
- Charging stations get verbose AI-generated descriptions ("Give a brief description of the following EV charging station...")
- Trip summary has "Charging up to 90.0%" noise
- Uses `###` subheadings throughout

**Requirement:** The journey section should be compact and polished:

1. **Leg table** — A clean table for way out and way home with columns: Leg, From → To, Distance, Arrival Battery. No `###` headings. No "Charging up to 90%" lines — the charging happens at each intermediate stop implicitly.

2. **Charging station list** — After the table, a simple bullet list of charging stations used (name + location). No AI-generated descriptions.

3. **Trip summary** — Keep the summary line (total distance, total duration, final arrival battery, departure/arrival time) but drop the verbose per-leg descriptions.

4. **Route maps** — Include the Folium route maps (`m_out`, `m_home`) in the PDF if possible. The notebook already generates them. They're currently displayed in the Gradio UI but not embedded in the PDF. Look into saving them as images (HTML → PNG via a headless browser, or use the Folium map's screenshot feature) and including them inline.

**Action:**
- Rewrite `status_out` and `status_home` generation to use a table format instead of `###` headings and verbose text
- Remove the `get_info` calls for charging station descriptions (lines 1171, 1240)
- Replace with a simple station name/location list
- Remove redundant "Charging up to X%" lines
- Investigate embedding the Folium maps as images in the PDF (save as PNG, include via LaTeX `\includegraphics`)

### 5. Departure location mismatch

- Aachen, Boulogne-sur-Mer, Köln use: `Leuvensesteenweg 431, 2812 Mechelen`
- Bielefeld, Dortmund use: `Heirweg 85A, 9190 Stekene, Belgium`

**Action:** Check what drives the departure address in the notebook. If it's a constant or env var, set it to the correct home address and re-generate the affected brochures.

### 6. Walking distances too long for "no strenuous activities"

The brief asks for relaxed walking but several restaurant recommendations are unreasonably far:
- Boulogne-sur-Mer: L'Îlot Vert — 29 min walk (2.0 km)
- Köln: Max Stark — 27 min walk (1.9 km)
- Bielefeld: Restaurant KDW — 25 min walk (1.7 km)

**Action:** Cap walk recommendations at ~20 minutes / 1.5 km max. Filter or re-prompt when the only nearby options exceed this. If the distance is too far or the weather is bad, suggest taking a taxi instead.

### 7. Restaurant selection section is too long and repetitive

Each brochure has a full "Restaurant selection" section that re-lists every restaurant with full descriptions — most of which were already mentioned in the itinerary. This bloats the PDFs unnecessarily (Aachen = 6.3 MB, Bielefeld = 3.9 MB).

**Action:** Trim the restaurant section to a compact format — e.g. name, cuisine, address, rating, walk time in a table or concise listing. Drop the redundant full descriptions.

### 8. Restaurant section formatting and permanently closed filter

**a) `###` restaurant names should be bold, not headings:** The restaurant name is currently formatted as `### {name}` (line 1374 in the notebook), which creates a `###` subheading. Change to `**{name}**` (bold), consistent with the "no `###` headings" rule.

**b) Permanently closed restaurants should be filtered out:** The Google Places API returns `permanently_closed: true` for closed businesses. The code fetches place details (via `get_google_place_details`) but doesn't check this field. Add `permanently_closed` to the fields list, and skip any restaurant where it's `true`.

**Action:**
1. In `get_google_place_details`, add `'permanently_closed'` to the requested fields
2. In the restaurant processing loop in `generate_restaurant_map_with_link`, filter out results where `r.get('permanently_closed')` is `True`
3. Change `### {r['name']}` → `**{r['name']}**`

### 9. Suspicious ratings from small sample sizes

Some restaurants have statistically meaningless ratings:
- Dortmund: Le Bon Filet Steakhouse — 5.0 / 81 reviews (opened March 2025)
- Boulogne-sur-Mer: Chez Sandrine — 4.9 / 20 reviews

**Action:** Add a minimum-review-count threshold (e.g. >= 100 reviews, or >= 50 for recently opened places). Filter out restaurants below the threshold.

### 10. Brochure size disparity across cities

- Aachen: 6.3 MB
- Bielefeld: 3.9 MB
- Dortmund: 1.6 MB
- Köln: 485 KB
- Boulogne-sur-Mer: 160 KB

The smaller brochures have noticeably thinner content — fewer restaurants, shorter city guide. This may be because the Tavily search returns less data for smaller cities, or the LLM token budget is the same for every city and it truncates when there's less to say.

**Action:** Either (a) set a minimum content length per section and re-prompt if under, or (b) vary the LLM response size request based on how much search context was returned.

### 11. Tourist Office section formatting is sloppy

The tourist office section has inconsistent formatting across brochures:
- Aachen: bare text with underlined links inline
- Boulogne-sur-Mer: address and links run together without spaces or line breaks (e.g. `Boulogne-sur-Mer30 Rue de la Lampe`)
- Köln: address and website name jumbled together (`KölnTourismus GmbH | VisitKöln Kardinal-Höffner-Platz 1`)

**Requirement:** The tourist office block should be formatted as a clean list with three items:
- Address (street, postal code, city, country)
- Website (clickable link)
- View on Google Maps (clickable link)

Example:
```
- *Address:* Kardinal-Höffner-Platz 1, 50667 Köln, Germany
- *Website:* [Visit Köln](https://www.koeln.de)
- *Google Maps:* [View on Map](https://maps.google.com/...)
```

**Action:** Fix the template or the LLM prompt that generates the tourist office section to always output a structured list.

### 12. Hotel section formatting is too sloppy

The hotel section varies widely across brochures:
- Aachen: hotel name and address on one line, then a wall of text with links scattered inline
- Boulogne-sur-Mer: address and description run together without clear separation
- Bielefeld: better than most, but links are still inline
- Köln: name and address line, then all text in one paragraph

**Requirement:** The hotel section should follow this clean structure:

1. **Hotel name** in bold (e.g. `**Hyatt Regency Cologne**`)
2. A bullet list with:
   - Address (street, postal code, city, country)
   - Website (clickable link)
   - View on Google Maps (clickable link)
3. A paragraph describing the hotel (amenities, unique features, check-in/out if notable)
4. *Optional:* A picture of the hotel front if available (via Google Places API or similar)

Example:
```
**Hyatt Regency Cologne**

- *Address:* Kennedy-Ufer 2A, 50679 Köln, Germany
- *Website:* [Hyatt Regency Cologne](https://www.hyatt.com/...)
- *Google Maps:* [View on Map](https://maps.google.com/...)

Hyatt Regency Cologne is a luxury riverside hotel set on the banks of the Rhine. It offers impressive views of the Cologne Cathedral and Old Town skyline...
```

**Action:** Restructure the hotel section template and the LLM prompt to output this format consistently across all brochures. Investigate whether the Google Places API can provide a hotel front photo for inclusion.

### 13. Typo: "depating" → "departing"

Present in multiple brochures:
> "When depating at 3:00 PM, arrival will be at: ..."

**Action:** Fix the source string in `travel_template.tex` (or whichever formatting function generates the trip summary).

### 14. Planner section: rewrite itinerary prompts with real user preferences

**Current issues with the planner (itinerary section):**

1. **AI intro/concluding remarks** — The LLM adds lead-ins like "Here is a wonderful weekend plan for..." or closings like "We hope you have a fantastic time!". These should never appear.

2. **Restaurant info is duplicated** — The planner references restaurants with full descriptions that are already in the restaurant section. Restaurant mentions in the itinerary should be minimal: just the **name** and a **one-line description** (e.g. cuisine type). No address, rating, walk time, website — that's all in the restaurant section.

3. **Detailed hours frame** — Current output has precise times like "5:00 PM - 6:00 PM: Pre-dinner drink..." Should use **time-of-day blocks** (morning, afternoon, evening) instead.

4. **The prompts don't match actual travel patterns** — The EVENING_TEMPLATE, ALL_DAY_TEMPLATE, and SUN_TEMPLATE need a complete rewrite.

**User's actual weekend pattern:**

**Friday (arrival 5-6 PM):**
- Arrive at hotel, refresh
- Have a drink in the bar/lobby, discuss options
- Short walk to get a first impression of the city (or take taxi if weather is bad)
- Dinner at a nearby restaurant
- Return to hotel for a nightcap and card game (UNO)

**Saturday:**
- Breakfast at hotel (9 AM - 11 AM)
- Sightseeing: walk around the city, local markets, tourist office, shopping (boutiques or mall), local café or beer hall / winestube
- Return to hotel around 5 PM
- Evening drink, dinner
- Return to hotel for nightcap and card game

**Sunday:**
- Breakfast at hotel (9 AM - 11 AM)
- Pack luggage, check out
- Walk in the city or surrounding area
- Depart so that arrival home is between 5-7 PM

**General preferences:**
- Budget: ~1500-2000 EUR for 3 people (hotel, dinner, drinks — shopping and car not included)
- Take taxi if the distance is too far or weather is bad
- Minimal stress, relaxed pace
- 4-5 star hotels only (3-star is not an option)

**Action:** Rewrite the three prompt templates and the main weekend_prompt:

1. Remove all references to specific clock times and durations ("about 1 hour", "about 3 hours", "from 11 AM until 5 PM"). Use time-of-day blocks (morning, afternoon, evening).
2. When referencing a restaurant in the itinerary, use only: `**Restaurant Name** (cuisine type, short tagline)`.
3. Add strong negative instructions: "Do NOT add any introductory welcome message, closing remarks, or 'I hope you enjoy' text. Start directly with Friday. End immediately after Sunday departure."
4. Embed the actual weekend pattern above verbatim as the required structure.
5. Include taxi fallback: "If the walk to a restaurant or attraction is too far (over 20 min) or the weather is bad, suggest taking a taxi."
6. Hotel quality: recommend 4-5 star hotels only. Budget guideline is ~1500-2000 EUR for 3 people (hotel, dinner, drinks).

### 15. Layout and style guidelines for the PDF

**Current issues with the LaTeX output:**

1. **TOC depth** — Currently set to `tocdepth=3` (line 1638 in `travel_template.tex`). Since `###` headings are banned, the TOC should only show 2 levels. Set `tocdepth=2` and `secnumdepth=2`.

2. **Page breaks splitting tables and lists** — When a restaurant listing or leg table spans two pages it becomes hard to read. Add `\usepackage{nowidow}` and `\usepackage{longtable}` to the LaTeX template. Increase `\widowpenalty` and `\clubpenalty` beyond current values.

3. **Paragraph breaks between name and details** — A restaurant name must not end up on one page with its details on the next. The `\needspace` command (already used in the template) should be applied to critical items.

4. **Figures floating away from reference** — Route maps and hotel photos should stay near where they are referenced, not float to a separate page. Ensure `\floatplacement{figure}{H}` (line 1807) works consistently.

5. **Emojis** — Should never appear in the final PDF. Add a post-processing filter to strip any emoji/emoticon characters from the markdown before pandoc conversion.

6. **Bold and italic discipline** — Current output overuses bold. Limit bold to: section headings (`##`), hotel names, restaurant names, and key numbers (battery %, distances, prices). **No italic text at all.**

7. **Verbose descriptions** — AI-generated descriptions (city guide, hotel, restaurants) sometimes meander. The prompt should insist on concise, direct sentences in active professional English. No filler phrases ("If you're looking for...", "Don't miss...", "This is a great option for...").

8. **Not everything should be a list** — Use structured paragraphs where appropriate. Lists for addresses, attributes, and sequential steps. Prose paragraphs for descriptions and narratives.

9. **Factual grounding** — All claims must be checked against the search context. Strengthen the "Use ONLY the verified search context" instruction with explicit examples of what not to invent: prices, opening hours, specific menu items unless confirmed.

**Action:**
- Set `tocdepth=2` and `secnumdepth=2` in `travel_template.tex`
- Add `\usepackage{nowidow}` and `\usepackage{longtable}` to the template
- Add emoji-stripping function to the markdown pipeline
- Tighten LLM prompts for city guide, hotel, and restaurant descriptions: concise, active English, bold only for key items, no italic
- Add explicit "do not hallucinate" examples to the fact-checking prompt instruction

---

## 🔧 Recommended approach

1. Fix the template typos and address formatting
2. Rewrite the planner prompts (issue 14 — highest impact on quality)
3. Add review-count threshold and walking-distance cap
4. Implement the selectable restaurant categories with cuisine filter
5. Clean up "Wining & Dining" to remove restaurant references
6. Consolidate on a single template style
7. Compact the restaurant listing format
8. Re-generate all brochures with the updated notebook
9. Do a size/content sanity check on each one after generation