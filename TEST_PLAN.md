# Test Plan — DBG Trip Planner


## Prerequisites

- Backend running: `cd backend && uvicorn main:app --port 8000`
- Frontend running: `cd frontend && npx vite`
- Valid API keys in `.env` (OpenRouter/OpenAI, Google Maps, ORS, Tavily)
- Pandoc + XeLaTeX installed (for PDF generation)

---

## 1. Backend Smoke Tests (via curl)

```bash
# Health
curl http://localhost:8000/api/health

# City Guide
curl -X POST http://localhost:8000/api/city-guide \
  -H "Content-Type: application/json" \
  -d '{"city":"Aachen","country":"Germany"}'

# Hotels
curl -X POST http://localhost:8000/api/hotels \
  -H "Content-Type: application/json" \
  -d '{"city":"Aachen"}'

# Describe Hotel (use a real place_id from hotels output)
curl -X POST http://localhost:8000/api/hotels/describe \
  -H "Content-Type: application/json" \
  -d '{"hotel":{"name":"Hotel Aachen","address":"Aachen, Germany","place_id":"...","latitude":50.77,"longitude":6.08,"star_rating":"4-star","review_rating":4.5,"website":"https://...","reviews_total":200}}'

# Restaurants
curl -X POST http://localhost:8000/api/restaurants \
  -H "Content-Type: application/json" \
  -d '{"hotel_address":"Hotel Aachen, Aachen, Germany","cuisines":["Local","Italian","Steakhouse"]}'

# Route
curl -X POST http://localhost:8000/api/route \
  -H "Content-Type: application/json" \
  -d '{"end_address":"Aachen, Germany","start_battery":90}'

# Plan Trip (uses station data from route)
curl -X POST http://localhost:8000/api/route/plan \
  -H "Content-Type: application/json" \
  -d '{"end_address":"Aachen, Germany","start_battery":90,"selected_stations_out":[{"brand":"Fastned","latitude":51.2,"longitude":5.5,"location":"Eindhoven"}],"selected_stations_home":[]}'

# Planner
curl -X POST http://localhost:8000/api/planner \
  -H "Content-Type: application/json" \
  -d '{"city":"Aachen","hotel_name":"Pullman Aachen","hotel_address":"Hotel Aachen","restaurant_list":"**Ristorante** (Italian, cozy atmosphere)","search_context":"Aachen has a historic cathedral and nice Christmas market."}'

# Generate PDF (test with minimal data)
curl -X POST http://localhost:8000/api/pdf \
  -H "Content-Type: application/json" \
  -d '{"city":"Aachen","country":"Germany","city_guide":"# Guide\n\nAachen is lovely.","tourist_office":"- *Address:* Aachen","hotel":"**Hotel**\n\nAddress","restaurants":"## Italian\n\n**Ristorante**","journey_out":"## Outbound\n\nTable","journey_home":"## Return\n\nNo stops","planner":"## Friday\n\nEvening"}'
```

**Expected results:**
- All endpoints return HTTP 200
- PDF endpoint returns `{"pdf_path": "...", "download_url": "..."}`
- PDF download URL returns a valid PDF file (Content-Type: application/pdf)

---

## 2. Frontend Tests (manual)

### 2.1 Navigation
- [ ] App loads at http://localhost:5173/
- [ ] Step bar shows 6 steps: City Guide → Hotel → Restaurants → Route → Itinerary → PDF
- [ ] Step highlight progresses correctly as each section completes

### 2.2 City Guide
- [ ] Enter city name, click "Generate City Guide"
- [ ] Loading spinner shows during backend call
- [ ] City guide markdown renders in left panel
- [ ] Tourist office info renders in right panel
- [ ] Error banner shows on API failure

### 2.3 Hotel Selection
- [ ] Click "Search Hotels" — hotels appear as clickable cards
- [ ] Select a hotel — loading indicator shows while description generates
- [ ] Hotel info renders as **bold name** + address/website/maps list

### 2.4 Restaurant Selection
- [ ] Cuisine pills are togglable (Local/Italian/Croatian/Grill/Steakhouse/Seafood)
- [ ] At least one cuisine selected before search
- [ ] Results show compact format: **bold name** + address + walk + rating
- [ ] Restaurants with < 50 reviews are excluded from results
- [ ] Restaurants > 1500m from hotel are excluded

### 2.5 EV Route Planning
- [ ] Enter destination city
- [ ] Route map displays with departure/destination markers
- [ ] Charging stations appear on map as markers
- [ ] Station pills are clickable to select for outbound/return

### 2.6 Trip Planning
- [ ] Select at least one outbound station
- [ ] Click "Plan Trip with Selected Stops"
- [ ] Leg tables appear as markdown tables
- [ ] Trip summary shows distance, duration, battery

### 2.7 Itinerary
- [ ] Click "Generate Itinerary"
- [ ] Output has: Friday Evening, Saturday, Sunday sections
- [ ] No clock times (only morning/afternoon/evening)
- [ ] Restaurant refs are **Name** (cuisine, short tagline) only
- [ ] No emoji, no italic, no "I hope you enjoy" fluff

### 2.8 PDF Generation
- [ ] Click "Generate PDF Brochure"
- [ ] Download link appears
- [ ] Downloaded PDF has cover page with DBG Travel branding
- [ ] TOC shows only 2 levels (sections and subsections)
- [ ] No ### headings in the PDF
- [ ] Tables render cleanly (leg tables, restaurant listings)
- [ ] No widows/orphans in text
- [ ] No emoji visible
- [ ] No italic text anywhere

---

## 3. Feature Verification (REQUIREMENTS.md items)

| # | Issue | Test |
|---|-------|------|
| 1 | Wining & Dining | City guide output has no specific restaurant names in that section |
| 2 | Cuisine selector | Only Local/Italian/Croatian/Grill/Steakhouse/Seafood appear in UI |
| 3 | Consistent format | All sections use `#` and `##` only, DBG Travel branding on cover |
| 3b | No ### headings | Search PDF for `###` — none found |
| 4 | Journey leg table | Output is `| Leg | From → To | Distance | Battery |` format |
| 5 | Departure address | Route default is Heirweg 85A, 9190 Stekene, Belgium |
| 6 | Walking cap | No restaurants > 1500m from hotel in results |
| 7 | Compact restaurants | Bold names, no verbose AI descriptions per restaurant |
| 8 | Closed + review filter | permanently_closed restaurants excluded; < 50 reviews excluded |
| 9 | Tourist office | Formatted as `- *Address:*`, `- *Website:*`, `- *Google Maps:*` |
| 10 | Hotel formatting | **bold name** + list (address, website, maps) + description |
| 11 | Typo | "departing" not "depating" |
| 12 | Planner pattern | Uses time-of-day blocks, no clock times, UNO/cards mentioned |
| 13 | LaTeX template | tocdepth=2, secnumdepth=2, nowidow package included |
| 14 | Brochure size | All brochures should be < 3 MB with consistent content density |
| 15 | Layout | No emoji, no italic, no "I hope you enjoy" |

---

## 4. Edge Cases

- [ ] Empty city name → button disabled / validation error
- [ ] Non-existent city → graceful error message
- [ ] No charging stations found → route still returns with warning
- [ ] No 4-5 star hotels in city center → informative message, not crash
- [ ] No restaurants matching all filters → empty list with message
- [ ] Very long city name → layout doesn't break
- [ ] Negative battery % → validation
- [ ] Battery > 100% → clamp or validate
- [ ] Network timeout → error banner, not hang

---

## 5. API Key Fallbacks

- [ ] OPENROUTER_API_KEY missing → falls back to OPENAI_API_KEY
- [ ] GOOGLE_MAPS_API_KEY missing → falls back to GOOGLE_API_KEY
- [ ] Missing keys → descriptive error messages in API response

---

## 6. Load & Performance

- [ ] City guide generates in < 30 seconds (Tavily 6 parallel searches + LLM)
- [ ] Google Places calls complete in < 5 seconds
- [ ] PDF generation completes in < 20 seconds
- [ ] Frontend bundle loads in < 2 seconds on fast connection