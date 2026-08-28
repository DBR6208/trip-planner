# Trip Planner — Rebuild (FastAPI + React/Vite)

## Architecture

```
myTrip_Planner/
├── backend/
│   ├── main.py              # FastAPI app, endpoint routing
│   ├── config.py            # API keys, constants
│   ├── requirements.txt     # Python deps
│   ├── services/
│   │   ├── city_guide.py    # Tavily search + LLM city guide generation
│   │   ├── geo.py           # Geocoding, ORS routing, distance calculations
│   │   ├── hotels.py        # Google Places hotel search + filters
│   │   ├── restaurants.py   # Google Places restaurant search + filters
│   │   ├── charging.py      # Charging station lookup, route planning
│   │   ├── planner.py       # Weekend itinerary LLM prompts
│   │   ├── pdf.py           # Markdown assembly + pandoc LaTeX PDF
│   │   └── tourist_office.py # Tourist info lookup
│   ├── templates/
│   │   └── travel_template.tex  # Clean LaTeX template
│   └── data/
│       └── unique_locations.csv # Charging stations
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── App.tsx          # Main app, tabs
│       ├── api/             # Backend API client (fetch wrappers)
│       ├── components/      # Reusable UI components
│       ├── pages/           # Tab pages
│       └── types/           # TypeScript types
└── .env                     # API keys (shared)
```

## Backend endpoints (FastAPI)

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/city-guide | Generate city guide + tourist office |
| POST | /api/hotels | Search 4-5 star hotels |
| POST | /api/restaurants | Search restaurants by cuisine, filtered |
| POST | /api/route | Calculate EV route + charging stations |
| POST | /api/route/plan | Plan trip with selected charging stops |
| POST | /api/planner | Generate weekend itinerary |
| POST | /api/pdf | Generate PDF brochure from all data |
| GET  | /api/map/route/{session} | Get route map HTML |

## Fixed issues (all 15 baked in)

1. Wining & Dining → horeca overview only (no specific restaurants)
2. Cuisine filter: Local/Italian/Croatian/Grill/Steakhouse/Seafood only
3. Consistent format (DBG Travel style)
3b. No ### headings anywhere
4. Leg table format, no verbose charging descriptions
5. Departure: Heirweg 85A, 9190 Stekene, Belgium
6. Walking cap: 1500m / ~20 min
7. Compact restaurant listings (bold name, table format)
8. permanently_closed filter + review threshold (>=50)
9. Tourist Office: structured address/website/maps list
10. Hotel: bold name + list + description
11. Typo fixed
12. Planner: actual weekend pattern, time-of-day blocks
13. tocdepth=2, nowidow, no emoji, no italic
14. Consistent brochure size
15. Layout: TOC depth 2, no widows/orphans, no emoji

## Data flow

1. User enters city, country in frontend
2. Frontend POSTs to /api/city-guide
3. Backend: Tavily parallel search → OpenAI/OpenRouter LLM → returns markdown
4. Frontend shows guide, then user selects hotel, cuisines, charging stops
5. Each step POSTs to backend
6. Final "Generate PDF" POSTs all state → backend assembles markdown → pandoc LaTeX PDF
7. PDF returned as download