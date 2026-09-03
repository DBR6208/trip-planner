# DBG Travel — Trip Planner

A weekend trip planner web application that generates branded PDF travel brochures. Enter your destination, and it produces a complete weekend guide with route planning, hotel recommendations, restaurant selection, sightseeing, and EV charging details — all formatted in the DBG Travel brand style.

## Modernization roadmap

The current application is being redesigned around a safer and more controlled
brochure workflow. The detailed implementation order and acceptance criteria are
in [PLAN.md](PLAN.md). The items in this section are planned capabilities; they
are not all available in the current codebase.

### Target workflow

1. Generate a first draft from the selected destination, hotel, restaurants,
   route, and itinerary.
2. Review and modify charging stops, then recalculate a battery-feasible route.
3. Choose a landmark-specific cover image from a labelled shortlist.
4. Edit one complete brochure document in an in-app Markdown editor.
5. Add controlled LaTeX-compatible layout blocks when needed.
6. Compile and inspect the PDF inline, then explicitly download the final copy.

### Current EV charging data (planned replacement)

`unique_locations.csv` is a legacy, approximately two-year-old dataset and will
not remain the primary charging source. The target primary provider is **TomTom
Long Distance EV Routing**, configured through:

```env
TOMTOM_API_KEY=...
CHARGING_PROVIDER=tomtom
```

`CHARGING_PROVIDER=tomtom` will use TomTom's battery-aware route calculation and
current station data. `CHARGING_PROVIDER=offline` will use the legacy CSV as a
clearly labelled non-live fallback.

The target Route step will propose suitable stops, favouring Circle K, IONITY,
Fastned, Allego, Shell, EnBW Mobility, and E.ON Drive when they are feasible.
The user will always be able to accept, add, remove, replace, or reorder stops,
change connector/power/network preferences, and set battery reserve targets.
Every edit will trigger a complete backend recalculation; an unreachable or
incompatible plan is shown as invalid instead of being silently changed.

When enabled for the TomTom account, the UI will show current connector
availability with a timestamp and a **Refresh live status** action. This is a
current snapshot, not a promise that a charger will be free on a future trip.

### Markdown editor and inline PDF preview (planned)

Generated content will become an editable first draft in a source-first
CodeMirror Markdown editor. The desktop UI will use a split view for Markdown
source, rendered preview, and PDF preview. PDF preview remains in the same
browser window; downloading happens only after an explicit click.

The editor will support an allowlisted set of Pandoc/LaTeX layout blocks, for
example:

````markdown
```{=latex}
\newpage
```
````

````markdown
```{=latex}
\begin{figure}[htbp]
\centering
\includegraphics[width=0.70\textwidth]{asset:hotel-photo}
\caption{Hotel exterior.}
\end{figure}
```
````

Only server-approved asset IDs and safe commands will be allowed. The planned
pipeline rejects arbitrary local paths, arbitrary URLs, untrusted HTML, and
dangerous LaTeX file/system commands.

### Landmark-first cover images (planned)

Cover selection will identify 3–5 canonical landmarks before searching for
images: for example Eiffel Tower for Paris, Cologne Cathedral/Kölner Dom for
Cologne, and Aachen Cathedral for Aachen. Candidate images will be retrieved
and ranked per landmark, then displayed with the landmark name, source, and
attribution for manual selection.

The priority sources are:

1. Google Places photos associated with a specific landmark.
2. Verified official city/tourism-board promotional imagery.
3. Wikimedia Commons/Wikidata media with license and attribution details.
4. Unsplash only as a generic aesthetic fallback with its required attribution.

Tavily will discover landmarks and official sources. Firecrawl is optional for
extracting imagery from a known, verified tourism page. Serper-style image
search may be used only as a labelled manual-selection fallback, not as an
automatic PDF image source.

### Optional local models (planned)

The Ubuntu deployment can optionally use Ollama and local Qwen models:

- Qwen3 4B Instruct for quick rewriting and Markdown assistance.
- Qwen3 8B Instruct as the default private/local brochure model.
- Qwen3 14B Instruct for slower on-demand complex editing.
- Qwen3-VL 4B Instruct for batch relevance ranking of filtered image thumbnails.

Local models assist with writing, structuring, and ranking. They do not replace
authoritative place/search data, routing, charging availability, licensing, or
final human editorial decisions. Cloud fallback must be an explicit user choice.

### Docker deployment (planned)

The deployment target is Docker Compose on Ubuntu:

```text
Browser -> Nginx/React frontend -> internal FastAPI API -> isolated PDF worker
                                                   -> optional internal Ollama
```

Only the frontend will expose a network port. Provider keys stay in backend
secrets, brochure files/assets use persistent named volumes, and the PDF worker
will run with strict resource limits and no open internet access during
compilation.

## Architecture

```
├── backend/          FastAPI (Python) — 13 API endpoints
│   ├── main.py       App entry point
│   ├── config.py     Constants, addresses, thresholds, model selection
│   ├── services/     9 service modules
│   │   ├── llm.py             LLM prompt orchestration (auto-fallback on overload)
│   │   ├── city_guide.py      City descriptions
│   │   ├── hotels.py          Hotel search, photos, indoor parking lookup, Folium maps
│   │   ├── restaurants.py     Restaurant search & filtering
│   │   ├── tourist_office.py  Tourist info + Folium map
│   │   ├── geo.py             Geocoding & maps
│   │   ├── charging.py        EV charging station lookup
│   │   ├── planner.py         Weekend itinerary generation
│   │   └── pdf.py             PDF generation (LaTeX → PDF)
│   └── templates/
│       └── travel_template.tex   LaTeX template
├── frontend/         React 19 + TypeScript 6 + Vite 8 + Tailwind 4
│   └── src/
│       ├── App.tsx    6-step wizard (Explore → Hotel → Restaurants → Route → Planning → Brochure)
│       └── index.css  DBG Travel brand theme (navy/gold)
├── docs/              Screenshots and documentation images
├── SESSION_CONTEXT.md  Session state tracking
├── REQUIREMENTS.md     Feature specification & issue tracking
└── myTripPlanner_V08.ipynb  Original Gradio notebook (frozen reference)
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- LaTeX installation (for PDF generation: `texlive-xetex`, `texlive-latex-extra`)

### Backend

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Create a `.env` file in the project root with your API keys:

```env
OPENROUTER_API_KEY=...          # LLM provider (default model: openai/gpt-4o)
TAVILY_API_KEY=...              # Web search context
ORS_API_KEY=...                 # OpenRouteService — routing & directions
GOOGLE_MAPS_API_KEY=...         # Places, hotel & restaurant details
```

The LLM routes through OpenRouter using `openai/gpt-4o` by default. You can change the model by setting `OPENROUTER_MODEL` in `.env`. If `OPENROUTER_API_KEY` is not set, it falls back to `OPENAI_API_KEY`.

Then start the server:

```bash
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### PDF Generation

PDFs are produced server-side via LaTeX (pandoc + xelatex). Ensure you have the required TeX packages:

```bash
sudo apt install texlive-xetex texlive-latex-extra pandoc
```

## Usage

1. Open the frontend (or call the API directly)
2. Enter your destination city
3. Select travel dates (Friday → Sunday)
4. Choose hotel preferences and restaurant cuisines
5. Generate your weekend itinerary
6. Download the PDF brochure

## Key Preferences

- Departure from: **Heirweg 85A, 9190 Stekene, Belgium**
- Hotels: 4–5 star only
- Cuisines: local, Italian, Croatian, grill, steakhouse, seafood
- Walking cap: 1.5 km (take taxi beyond that)
- Weekend: Friday 5–6 PM arrival → Sunday 5–7 PM return home
- Budget: ~€1500–2000 for 3 people (hotel, dinner, drinks)

## Tech Stack

- **Backend:** FastAPI, OpenRouter (GPT-4o), Google Maps API, OpenRouteService, Tavily Search
- **Frontend:** React 19, TypeScript 6, Vite 8, Tailwind 4, DaisyUI, react-markdown
- **PDF:** LaTeX via pandoc + xelatex

## Screenshots

| Explore tab | Hotel tab |
|:---:|:---:|
| ![Explore tab](docs/explore-tab.png) | ![Hotel tab](docs/hotel-tab.png) |
