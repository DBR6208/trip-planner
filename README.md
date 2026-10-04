# DBG Travel — Trip Planner

A weekend trip planner web application that generates branded PDF travel brochures. Enter a destination and the app produces a complete weekend guide with city research, hotel recommendations, restaurant selection, EV route planning, day-by-day itinerary, and a printable brochure.

---

## Architecture

```
frontend/                 React 19 + TypeScript 6 + Vite 8 + Tailwind 4 + DaisyUI
backend/                  FastAPI (Python 3.11+)
├── main.py               App entry point — 19 API endpoints
├── config.py             API keys, thresholds, routes, constants
├── services/             Domain and rendering service modules
│   ├── llm.py            LLM orchestration with auto-fallback
│   ├── city_guide.py     Tavily search + LLM city guide generation
│   ├── hotels.py         Google Places hotel search + Folium maps + parking
│   ├── restaurants.py    Google Places search → filters → LLM cuisine classification + Folium
│   ├── tourist_office.py Tourist info lookup + Folium map
│   ├── geo.py            Geocoding, ORS routing, Google Maps URLs
│   ├── charging.py       EV charging BFS route planner + ORS distance matrix
│   ├── planner.py        Weekend itinerary via LLM
│   ├── pdf.py            Markdown assembly → Pandoc → editable .typ/.tex → PDF
│   └── cover_images.py   Wikipedia + Tavily + Bing cover image search
├── templates/
│   ├── travel_template.tex  XeLaTeX brochure template (default / rollback)
│   └── travel_template.typ  Typst brochure template (opt-in)
├── filters/
│   └── typst_layout.lua  Pandoc layout blocks → Typst page/card controls
└── static/               Static assets (logo, etc.)
```

### Data Flow

1. Enter a destination city → backend fetches city guide + tourist office info
2. Select hotel → Google Places search filtered to 4-5 star, indoor parking lookup
3. Tick at least one cuisine → wide Google Places search, generic filters (chains, bars, fast food, excluded cuisines, 4.1+ rating, 50+ reviews, max 2.5 km), then one LLM pass that decides each place's real cuisine and keeps 0–5 per cuisine
4. Plan route → BFS over ORS distance matrix finds optimal EV charging stops
5. Generate itinerary → LLM builds Friday–Sunday plan using real weekend pattern
6. Create brochure → markdown assembled → CodeMirror editor (editable) → Pandoc → `brochure.typ` / `brochure.tex` (kept on disk, hand-editable) → PDF

---

## Tech Stack

| Layer       | Technology                                |
|-------------|-------------------------------------------|
| Backend     | FastAPI, OpenRouter (content model), httpx |
| Maps        | Folium, OpenStreetMap, Leaflet, BeautifyIcon |
| Routing     | OpenRouteService (ORS)                    |
| Places      | Google Maps / Places API                  |
| Search      | Tavily Search API                         |
| Images      | Wikimedia Commons, Tavily, Bing           |
| Frontend    | React 19, TypeScript 6, Vite 8, Tailwind 4, DaisyUI |
| PDF         | Pandoc + XeLaTeX (default) or Typst, Ghostscript compression |
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
| POST   | `/api/restaurants`      | Find restaurants near hotel for the ticked cuisines (at least one required, otherwise HTTP 400) + map |

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
| POST   | `/api/pdf`                        | Generate PDF with configured XeLaTeX or Typst renderer; also writes the editable `brochure.typ` / `brochure.tex` + images to `guides/source/{city}/` |
| POST   | `/api/pdf/rebuild`                | Recompile the hand-edited `brochure.typ` / `brochure.tex` into a new PDF (compiler errors are returned) |
| GET    | `/api/pdf/source?city=`           | Download the brochure source folder (source file + images) as a zip |
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
- `PDFPreview.tsx` — EmbedPDF viewer (fit-to-width, vertical scroll)

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Pandoc and a XeLaTeX distribution for the default PDF renderer
- Typst for the opt-in Typst PDF renderer
- A Chromium-compatible browser for Playwright map screenshots
- Ghostscript for PDF compression (optional)

The app can run without the optional PDF tooling, but generating a full brochure PDF requires Pandoc, a configured renderer (XeLaTeX by default or Typst), and a browser available to Playwright.

### Unix / macOS

#### 1. Install system dependencies

On Debian/Ubuntu, install the PDF dependencies with:

```bash
sudo apt update
sudo apt install texlive-xetex texlive-latex-extra pandoc fonts-font-awesome ghostscript
```

On macOS, install Pandoc, a TeX distribution that includes XeLaTeX (such as MacTeX), and optionally Ghostscript using your preferred package manager.

For the optional Typst renderer, install Typst with your preferred package manager, for example `brew install typst`.

#### 2. Create and install the backend environment

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m playwright install chromium
```

#### 3. Configure API keys

Create `.env` in the project root:

```env
OPENROUTER_API_KEY=...       # LLM provider (OpenAI-compatible)
TAVILY_API_KEY=...           # Web search + cover image search
ORS_API_KEY=...              # OpenRouteService routing
GOOGLE_MAPS_API_KEY=...      # Google Places API
```

#### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

#### 5. Start the frontend in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend is available at `http://localhost:8000`, with interactive API documentation at `http://localhost:8000/docs`.

### Windows (PowerShell)

#### 1. Install system dependencies

- Install Python 3.11+ and Node.js 18+.
- Install Pandoc.
- Install a TeX distribution with XeLaTeX, such as MiKTeX or TeX Live.
- Install Typst if you want to use the optional Typst renderer: `winget install typst`.
- Optionally install Ghostscript for PDF compression.

Ensure the installed command-line tools are on your `PATH`, then open a new PowerShell terminal.

#### 2. Create and install the backend environment

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r backend\requirements.txt
py -m playwright install chromium
```

If PowerShell reports that script execution is disabled when activating the environment, apply this setting only to the current PowerShell session and retry activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

#### 3. Configure API keys

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=...       # LLM provider (OpenAI-compatible)
TAVILY_API_KEY=...           # Web search + cover image search
ORS_API_KEY=...              # OpenRouteService routing
GOOGLE_MAPS_API_KEY=...      # Google Places API
```

#### 4. Start the backend

```powershell
.\.venv\Scripts\Activate.ps1
py -m uvicorn backend.main:app --reload --port 8000
```

#### 5. Start the frontend in a second PowerShell terminal

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend is available at `http://localhost:8000`, with interactive API documentation at `http://localhost:8000/docs`.

---

## Key Configuration (`backend/config.py`)

| Constant                     | Default                          | Description                         |
|-----------------------------|-----------------------------------|-------------------------------------|
| `HOME_ADDRESS`              | Heirweg 85A, 9190 Stekene, Belgium | Departure address for EV routing   |
| `WALK_DISTANCE_MAX_METERS`  | 2500                             | Maximum straight-line hotel distance (m); taxi is acceptable |
| `REVIEW_MINIMUM`            | 50                               | Minimum Google reviews count        |
| `EXCLUDED_CUISINE_KEYWORDS` | Turkish, Greek, Asian, … (DE/FR/NL spellings) | Names, websites and web evidence containing these are dropped |
| `KNOWN_CHAINS`              | L'Osteria, Vapiano, …            | Chains left out (repeated brands in the results are also detected automatically) |
| `BATTERY_CAPACITY_KWH`      | 78.0                             | EV battery capacity                 |
| `CONSUMPTION_KWH_PER_100KM` | 17.31                            | EV consumption rate                 |
| `CHARGE_UP_TO_PERCENT`      | 90.0                             | Target charge level                 |

---

## PDF Pipeline

1. `build_markdown(data)` — assembles editable brochure Markdown and inserts `<!-- pagebreak -->` directives before brochure sections and restaurant cuisine groups. The Restaurant tab itself remains free of page-break directives.
2. `generate_pdf(md, city, ...)` — converts the Markdown with Pandoc into `brochure.typ` or `brochure.tex` (per `PDF_ENGINE`) inside `guides/source/{city}/` and compiles it:
   - Inject cover image (JPEG/PNG only)
   - Screenshot restaurant map via Playwright Chromium (embedded as PNG) with a legend that lists only the cuisines on the map
   - Download and embed hotel photo
3. `rebuild_from_source(city)` — recompiles the (hand-edited) source file without touching the Markdown
4. `compress_pdf(pdf_path)` — optional Ghostscript compression (non-blocking)

PDFs are saved to `guides/temp/` during generation. Call `POST /api/pdf/finalize` to copy to `guides/{city}.pdf` and clean the temp directory (`guides/source/` is kept).

## Restaurant Selection Pipeline

`find_restaurants()` in `backend/services/restaurants.py`:

1. **Search** — one Google Places text search per ticked cuisine (3 pages of 20, English queries from `CUISINE_QUERY_MAP`, centred on the hotel). Results are merged by `place_id`; the search that found a place is only a hint.
2. **Pre-filter** (no extra API calls) — must be a food place, not a blocked name/type (fast food, bakery, café…), not an excluded cuisine, not a chain (`KNOWN_CHAINS` or the same brand appearing more than once), rating ≥ 4.1, reviews ≥ `REVIEW_MINIMUM`, and within `WALK_DISTANCE_MAX_METERS` (2.5 km). The pool is capped at 48, with 5 slots reserved per ticked cuisine.
3. **Enrich** — walking times, Google details (website, reviews, summary) and Tavily web evidence per candidate.
4. **One LLM pass** — decides each candidate's real cuisine (`CUISINE_HINTS`) and rejects chains, pizza/pasta-only menus, pubs and bars, fast food and excluded cuisines. It returns 0–5 per cuisine and is told not to pad. A cuisine that comes back empty gets one focused retry over its own unused candidates.
5. **Fallback** — if the LLM call fails, the best-rated places per search hint are used.

The selectable cuisines are the keys of `CUISINE_COLORS` (backend) and `CUI_COLORS` (`frontend/src/App.tsx`); keep both in sync. The PDF map legend is built from the same colours.

### Renderer configuration and rollback

The default remains the established XeLaTeX renderer:

```env
PDF_ENGINE=xelatex
```

To evaluate the Typst layout, install Typst and set:

```env
PDF_ENGINE=typst
```

Switching `PDF_ENGINE` back to `xelatex` is the immediate rollback path. The XeLaTeX template remains at `backend/templates/travel_template.tex`; the Typst template is `backend/templates/travel_template.typ`.

The Typst template builds in these layout defaults:

- hotel photos and restaurant maps are centered;
- restaurant cards stay together when a complete card fits on a page;
- restaurant cuisine groups start with an editable page-break directive.

#### Editing the .typ / .tex source by hand

Every **Generate PDF** also keeps the intermediate source: `brochure.typ` (Typst) or `brochure.tex` (XeLaTeX, depending on `PDF_ENGINE`) plus its images (`cover-image.*`, `logo.*`, hotel photo, `map-restaurants.png`) in `guides/source/{city}/`. Edit that file in any editor, save, then click **Rebuild PDF from brochure.typ** in the Brochure tab (or `POST /api/pdf/rebuild`) to recompile it. Compiler errors are shown in the app. Regenerating from the Markdown replaces the folder, and the previous version is kept once as `guides/source/{city}_previous/` so hand edits are not lost. Rebuilding needs `typst` (Typst) or `xelatex` (XeLaTeX) on the PATH.

Layout values (hotel photo 45% wide and centred, full-width restaurant map, cards kept together, fixed spacing) are constants in `LAYOUT_SETTINGS` in `backend/services/pdf.py`. Page breaks are deliberately manual: edit the visible `<!-- pagebreak -->` comments in the brochure Markdown, then regenerate the preview. These directives are hidden in rendered previews and are never included in the Restaurants tab.

### XeLaTeX Template (`travel_template.tex`)

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