# DBG Travel — Trip Planner

A weekend trip planner web application that generates branded PDF travel brochures. Enter a destination and the app produces a complete weekend guide with city research, hotel recommendations, restaurant selection, EV route planning, day-by-day itinerary, and a printable brochure.

---

## Architecture

```
frontend/                 React 19 + TypeScript 6 + Vite 8 + Tailwind 4 + DaisyUI
backend/                  FastAPI (Python 3.11+)
├── main.py               App entry point — 18 API endpoints
├── config.py             API keys, thresholds, routes, constants
├── services/             10 service modules
│   ├── llm.py            LLM orchestration with auto-fallback
│   ├── city_guide.py     Tavily search + LLM city guide generation
│   ├── hotels.py         Google Places hotel search + Folium maps + parking
│   ├── restaurants.py    Google Places + cuisine filter + walking cap + Folium
│   ├── tourist_office.py Tourist info lookup + Folium map
│   ├── geo.py            Geocoding, ORS routing, Google Maps URLs
│   ├── charging.py       EV charging BFS route planner + ORS distance matrix
│   ├── planner.py        Weekend itinerary via LLM
│   ├── pdf.py            Markdown assembly → pandoc + XeLaTeX → PDF
│   └── cover_images.py   Wikipedia + Tavily + Bing cover image search
├── templates/
│   └── travel_template.tex  LaTeX brochure template
└── static/               Static assets (logo, etc.)
```

### Data Flow

1. Enter a destination city → backend fetches city guide + tourist office info
2. Select hotel → Google Places search filtered to 4-5 star, indoor parking lookup
3. Choose cuisines → restaurants filtered by cuisine, walking cap (1.5 km), min reviews (50)
4. Plan route → BFS over ORS distance matrix finds optimal EV charging stops
5. Generate itinerary → LLM builds Friday–Sunday plan using real weekend pattern
6. Create brochure → markdown assembled → CodeMirror editor (editable) → pandoc + XeLaTeX → PDF

---

## Tech Stack

| Layer       | Technology                                |
|-------------|-------------------------------------------|
| Backend     | FastAPI, OpenRouter (GPT-4o-mini), httpx   |
| Maps        | Folium, OpenStreetMap, Leaflet, BeautifyIcon |
| Routing     | OpenRouteService (ORS)                    |
| Places      | Google Maps / Places API                  |
| Search      | Tavily Search API                         |
| Images      | Wikimedia Commons, Tavily, Bing           |
| Frontend    | React 19, TypeScript 6, Vite 8, Tailwind 4, DaisyUI |
| PDF         | Pandoc + XeLaTeX, Ghostscript compression |
| Editor      | CodeMirror 6 (@codemirror/lang-markdown)   |
| PDF Viewer  | EmbedPDF (@embedpdf/react-pdf-viewer)     |

---

## Backend Endpoints (FastAPI)

All endpoints are at `http://localhost:8000`. API docs at `/docs`.

### City & Tourist Office

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/api/city-guide`       | Generate city guide + tourist office info + map + photos |
| POST   | `/api/cover-images`     | Search cover images (Wikipedia, Tavily, tourist website) |
| POST   | `/api/cover-images/upload` | Upload a user cover image (multipart)                |
| POST   | `/api/cover-images/from-url` | Download an image from a URL as cover              |
| GET    | `/api/pdf/cover/{filename}` | Serve a user-uploaded cover image                   |

### Hotels

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/api/hotels`           | Search 4-5 star hotels + generate hotel map             |
| POST   | `/api/hotels/map`       | Regenerate hotel map (with optional selection + parking) |
| POST   | `/api/hotels/describe`  | Get LLM description + parking info for a specific hotel  |

### Restaurants

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/api/restaurants`      | Find restaurants near hotel (cuisine filter, walk cap, min reviews) + map |

### Route & Charging

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/api/route`            | Calculate route + find charging stations + route map     |
| POST   | `/api/route/plan`       | Plan trip with user-selected charging stops              |

### Itinerary

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/api/planner`          | Generate Friday–Sunday weekend itinerary                |

### Brochure / PDF

| Method | Path                              | Description                                     |
|--------|-----------------------------------|-------------------------------------------------|
| POST   | `/api/brochure/markdown`          | Assemble brochure markdown (no PDF compilation) |
| POST   | `/api/pdf`                        | Generate full PDF (pandoc → XeLaTeX)           |
| GET    | `/api/pdf/preview/{filename}`     | Serve PDF for inline preview                    |
| GET    | `/api/pdf/download-attachment/{filename}` | Download PDF as attachment           |
| POST   | `/api/pdf/finalize`               | Copy PDF from temp/ → guides/{city}.pdf + clean temp |

### Health

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| GET    | `/api/health`           | Health check → `{"status":"ok","timestamp":"..."}`      |

---

## Frontend Tabs & Components

The UI is a 6-step wizard — each tab depends on data from the previous step.

| Tab # | Tab          | Component / Feature              | Depends On              |
|-------|--------------|----------------------------------|-------------------------|
| 0     | Explore      | City guide + tourist office map  | — (start here)          |
| 1     | Hotel        | Hotel list + Folium map + parking| City guide loaded       |
| 2     | Restaurants  | Cuisine filter + restaurant list + map | Hotel selected    |
| 3     | Route        | EV route + charging stops + map  | — (works standalone)    |
| 4     | Planning     | Weekend itinerary generation     | Hotel selected          |
| 5     | Brochure     | Cover image gallery + CodeMirror editor + PDF preview + download | All above |

**Components:**
- `MarkdownEditor.tsx` — CodeMirror 6 (light theme, markdown language)
- `PDFPreview.tsx` — EmbedPDF viewer (125% zoom, vertical scroll)
- `HtmlPreview.tsx` — Rendered markdown preview (react-markdown)

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- LaTeX: `texlive-xetex`, `texlive-latex-extra`, `pandoc`, `fonts-font-awesome`
- Ghostscript (`gs`) for PDF compression (optional)

Install LaTeX packages:
```bash
sudo apt install texlive-xetex texlive-latex-extra pandoc fonts-font-awesome
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt
```

Create `.env` in the project root:
```env
OPENROUTER_API_KEY=...       # LLM provider (OpenAI-compatible)
TAVILY_API_KEY=...           # Web search + cover image search
ORS_API_KEY=...              # OpenRouteService routing
GOOGLE_MAPS_API_KEY=...      # Google Places API
```

Start:
```bash
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Key Configuration (`backend/config.py`)

| Constant                     | Default                          | Description                         |
|-----------------------------|-----------------------------------|-------------------------------------|
| `HOME_ADDRESS`              | Heirweg 85A, 9190 Stekene, Belgium | Departure address for EV routing   |
| `ALLOWED_CUISINES`          | Local, Italian, Croatian, Grill, Steakhouse, Seafood | Only these appear in brochures |
| `WALK_DISTANCE_MAX_METERS`  | 1500                             | Max walking distance ~20 min       |
| `REVIEW_MINIMUM`            | 50                               | Minimum Google reviews count        |
| `BATTERY_CAPACITY_KWH`      | 78.0                             | EV battery capacity                 |
| `CONSUMPTION_KWH_PER_100KM` | 17.31                            | EV consumption rate                 |
| `CHARGE_UP_TO_PERCENT`      | 90.0                             | Target charge level                 |

---

## PDF Pipeline

1. `build_markdown(data)` — assembles markdown from trip data with `\newpage` section breaks
2. `generate_pdf(md, city, ...)` — runs `pandoc` with `travel_template.tex`:
   - Inject cover image (JPEG/PNG only)
   - Screenshot restaurant map via Playwright Chromium (embedded as PNG)
   - Download and embed hotel photo
3. `compress_pdf(pdf_path)` — optional Ghostscript compression (non-blocking)

PDFs are saved to `guides/temp/` during generation. Call `POST /api/pdf/finalize` to copy to `guides/{city}.pdf` and clean the temp directory.

### LaTeX Template (`travel_template.tex`)

- DBG Travel branded title page with logo and cover image
- `tocdepth=2` (no subsubsections in TOC)
- `nowidow` package prevents orphaned lines
- `\detokenize{}` around image paths to handle underscores
- Font Awesome icons for cuisine markers in the restaurant legend

---

## Screenshots

### 1. Explore

The Explore tab is the starting point. Enter a city and country, then the app generates the destination guide and tourist-office context.

![Explore tab](screenshots/Screenshot01.png)

### 2. Destination Guide

After the city is loaded, the view expands into a full city guide with background information, top attractions, and a tourist-office map.

![City guide and tourist office](screenshots/Screenshot02.png)

### 3. Hotel Selection

The Hotel tab shows candidate hotels on the map and in a ranked list, with detailed property information and photos.

![Hotel tab](screenshots/Screenshot03.png)

### 4. Restaurant Selection

The Restaurants tab filters venues by cuisine, displays them on the map, and shows walking distance, rating, and detail cards for each option.

![Restaurants tab](screenshots/Screenshot04.png)

### 5. Route Planning

The Route tab builds an EV-friendly driving plan with charging stops, outbound and return leg summaries, and a route map.

![Route tab](screenshots/Screenshot05.png)

### 6. Weekend Planning

The Planning tab generates the day-by-day weekend itinerary.

![Planning tab](screenshots/Screenshot06.png)

### 7. Brochure Creation

The Brochure tab lets you choose a cover image, edit the markdown, and generate the final PDF brochure.

![Brochure tab](screenshots/Screenshot07.png)