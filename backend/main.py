"""Trip Planner — FastAPI Backend."""

import os
import tempfile
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import HOME_ADDRESS, OUTPUT_DIR
from .services import (
    city_guide as guide_svc,
    geo,
    hotels as hotel_svc,
    restaurants as restaurant_svc,
    tourist_office as to_svc,
    charging as charging_svc,
    planner as planner_svc,
    pdf as pdf_svc,
    llm,
)

app = FastAPI(title="DBG Trip Planner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── API Models ──

class CityGuideRequest(BaseModel):
    city: str
    country: str


class CityGuideResponse(BaseModel):
    city_guide: str
    tourist_office: str
    tourist_office_data: dict | None


class HotelSearchRequest(BaseModel):
    city: str


class HotelSearchResponse(BaseModel):
    hotels: list[dict]


class HotelDescriptionRequest(BaseModel):
    hotel: dict


class HotelDescriptionResponse(BaseModel):
    description: str
    formatted: str


class RestaurantSearchRequest(BaseModel):
    hotel_address: str
    cuisines: list[str]


class RestaurantSearchResponse(BaseModel):
    restaurants: list[dict]
    formatted: str


class RouteRequest(BaseModel):
    start_address: str = HOME_ADDRESS
    end_address: str
    start_battery: float = 90.0


class RouteResponse(BaseModel):
    map_html: str
    distance_km: float
    arrival_battery: float
    start_coords: list | None = None
    end_coords: list | None = None
    stations: list[dict]


class PlanTripRequest(BaseModel):
    start_address: str = HOME_ADDRESS
    end_address: str
    start_battery: float = 90.0
    selected_stations_out: list[dict]
    selected_stations_home: list[dict] | None = None


class PlannerRequest(BaseModel):
    city: str
    hotel_name: str
    hotel_address: str
    restaurant_list: str
    search_context: str


class PDFRequest(BaseModel):
    city: str
    country: str
    city_guide: str
    tourist_office: str
    hotel: str
    restaurants: str
    journey_out: str
    journey_home: str
    planner: str
    cover_image: str | None = None


# ── Endpoints ──

@app.post("/api/city-guide", response_model=CityGuideResponse)
def get_city_guide(req: CityGuideRequest):
    """Generate city guide + tourist office info."""
    try:
        guide = guide_svc.generate_city_guide(req.city, req.country)
        office = to_svc.find_tourist_office(req.city)
        formatted_to = to_svc.format_tourist_office(office) if office else ""
        return CityGuideResponse(
            city_guide=guide,
            tourist_office=formatted_to,
            tourist_office_data=office,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hotels", response_model=HotelSearchResponse)
def search_hotels(req: HotelSearchRequest):
    """Search 4-5 star hotels in a city."""
    try:
        hotels = hotel_svc.find_hotels(req.city)
        return HotelSearchResponse(hotels=hotels)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hotels/describe", response_model=HotelDescriptionResponse)
def describe_hotel(req: HotelDescriptionRequest):
    """Get LLM description for a hotel and format it."""
    try:
        h = req.hotel
        desc = llm.generate_with_search(
            f"Give a brief description of the hotel {h.get('name')} at {h.get('address')}",
            search_context="",
        )
        formatted = hotel_svc.format_hotel(h, desc)
        return HotelDescriptionResponse(description=desc, formatted=formatted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/restaurants", response_model=RestaurantSearchResponse)
def search_restaurants(req: RestaurantSearchRequest):
    """Find restaurants near hotel with cuisine/walking/review filters."""
    try:
        coords = geo.get_google_coords(req.hotel_address)
        if not coords:
            raise HTTPException(status_code=400, detail="Could not geocode hotel address")
        city = geo.get_city_from_coords(coords[0], coords[1])
        restaurants = restaurant_svc.find_restaurants(coords, req.cuisines, city)
        formatted = restaurant_svc.format_restaurants(restaurants)
        return RestaurantSearchResponse(restaurants=restaurants, formatted=formatted)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/route", response_model=RouteResponse)
def find_route(req: RouteRequest):
    """Calculate route, find charging stations."""
    try:
        result = charging_svc.find_route_and_stations(
            req.start_address, req.end_address, req.start_battery,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return RouteResponse(
            map_html=result["map_html"],
            distance_km=result["distance_km"],
            arrival_battery=result["arrival_battery"],
            start_coords=list(result.get("start_coords", [])),
            end_coords=list(result.get("end_coords", [])),
            stations=result.get("stations", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/route/plan")
def plan_trip(req: PlanTripRequest):
    """Plan trip with selected charging stops."""
    try:
        result = charging_svc.plan_trip_with_stops(
            req.start_address, req.end_address, req.start_battery,
            req.selected_stations_out, req.selected_stations_home,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/planner")
def get_planner(req: PlannerRequest):
    """Generate weekend itinerary."""
    try:
        itinerary = planner_svc.generate_itinerary(
            req.city, req.hotel_name, req.hotel_address,
            req.restaurant_list, req.search_context,
        )
        return {"itinerary": itinerary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pdf")
def generate_pdf(req: PDFRequest):
    """Generate full PDF brochure from all data."""
    try:
        data = {
            "city_guide": req.city_guide,
            "tourist_office": req.tourist_office,
            "hotel": req.hotel,
            "restaurants": req.restaurants,
            "journey_out": req.journey_out,
            "journey_home": req.journey_home,
            "planner": req.planner,
        }
        md = pdf_svc.build_markdown(data)
        pdf_path = pdf_svc.generate_pdf(
            md, req.city, req.country, req.cover_image,
        )
        return {"pdf_path": pdf_path, "download_url": f"/api/pdf/download/{os.path.basename(pdf_path)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf/download/{filename}")
def download_pdf(filename: str):
    """Download a generated PDF."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}