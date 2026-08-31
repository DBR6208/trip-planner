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
    tourist_office_map: str = ""


class HotelSearchRequest(BaseModel):
    city: str


class HotelSearchResponse(BaseModel):
    hotels: list[dict]
    map_html: str = ""


class HotelMapRequest(BaseModel):
    hotels: list[dict]
    tourist_office: dict | None = None
    selected_hotel_id: str | None = None


class HotelMapResponse(BaseModel):
    map_html: str


class HotelDescriptionRequest(BaseModel):
    hotel: dict


class HotelDescriptionResponse(BaseModel):
    description: str
    formatted: str


class RestaurantSearchRequest(BaseModel):
    hotel_address: str
    cuisines: list[str]
    hotel: dict | None = None


class RestaurantSearchResponse(BaseModel):
    restaurants: list[dict]
    formatted: str
    map_html: str = ""


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
        to_map = to_svc.generate_tourist_office_map(req.city, office) if office else ""
        return CityGuideResponse(
            city_guide=guide,
            tourist_office=formatted_to,
            tourist_office_data=office,
            tourist_office_map=to_map,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hotels", response_model=HotelSearchResponse)
def search_hotels(req: HotelSearchRequest):
    """Search 4-5 star hotels in a city + generate hotel map."""
    try:
        hotels = hotel_svc.find_hotels(req.city)
        office = to_svc.find_tourist_office(req.city)
        map_html = hotel_svc.generate_hotel_map(
            hotels, tourist_office=office, selected_hotel_id=None
        )
        return HotelSearchResponse(hotels=hotels, map_html=map_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hotels/map", response_model=HotelMapResponse)
def hotel_map(req: HotelMapRequest):
    """Generate / regenerate hotel map with optional selection + parking markers."""
    try:
        # Fetch parkings when a hotel is selected
        parkings = None
        if req.selected_hotel_id:
            for h in req.hotels:
                if h.get("place_id") == req.selected_hotel_id:
                    parkings = hotel_svc._find_nearby_parking(
                        h.get("name", ""), h.get("latitude", 0), h.get("longitude", 0)
                    )
                    break

        map_html = hotel_svc.generate_hotel_map(
            req.hotels,
            tourist_office=req.tourist_office,
            selected_hotel_id=req.selected_hotel_id,
            parkings=parkings,
        )
        return HotelMapResponse(map_html=map_html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hotels/describe", response_model=HotelDescriptionResponse)
def describe_hotel(req: HotelDescriptionRequest):
    """Get LLM description for a hotel — search the web + parking data, then generate."""
    try:
        h = req.hotel
        city = geo.get_city_from_coords(h.get("latitude", 0), h.get("longitude", 0)) or ""
        context = hotel_svc._tavily_search_hotel(h.get("name", ""), city)
        parkings = hotel_svc._find_nearby_parking(
            h.get("name", ""), h.get("latitude", 0), h.get("longitude", 0)
        )

        llm_prompt = (
            f"Describe the hotel {h.get('name')} at {h.get('address')} in {city}. "
            f"Use the web research context below for factual details. "
            f"Structure your description with these sections:\n"
            f"1. **Overview** — a 2-3 sentence general description of the hotel.\n"
            f"2. **Cleanliness** — what guests say about cleanliness and maintenance.\n"
            f"3. **Bars / Lounge** — does the hotel have a bar, lounge, or rooftop bar?\n"
            f"4. **Restaurants** — on-site restaurants, breakfast quality, dining options.\n"
            f"5. **Parking** — does the hotel offer on-site parking? Is it indoor, "
            f"does it require reservation, is it guaranteed or limited? "
            f"Describe the on-site parking situation only — do NOT list nearby garages.\n"
            f"Keep each section concise (1-2 sentences). No introductory or closing fluff. "
            f"No emoji, no italic. Bold only for the section labels (Overview, Cleanliness, etc.)."
        )
        desc = llm.generate_with_search(
            llm_prompt,
            search_context=context,
        )
        formatted = hotel_svc.format_hotel(h, desc, parkings=parkings)
        return HotelDescriptionResponse(description=desc, formatted=formatted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/restaurants", response_model=RestaurantSearchResponse)
def search_restaurants(req: RestaurantSearchRequest):
    """Find restaurants near hotel with cuisine/walking/review filters + map."""
    try:
        coords = geo.get_google_coords(req.hotel_address)
        if not coords:
            return RestaurantSearchResponse(
                restaurants=[], formatted="Could not locate hotel address."
            )
        city = geo.get_city_from_coords(coords[0], coords[1]) or ""
        cuisines = req.cuisines or ["Local", "Italian", "Croatian", "Grill", "Steakhouse", "Seafood"]
        restaurants = restaurant_svc.find_restaurants(coords, cuisines, city)
        formatted = restaurant_svc.format_restaurants(restaurants)

        # Generate map with hotel marker + restaurant markers
        hotel = req.hotel or {"latitude": coords[0], "longitude": coords[1], "name": "Hotel"}
        if hotel.get("latitude") is None:
            hotel["latitude"] = coords[0]
            hotel["longitude"] = coords[1]
        map_html = restaurant_svc.generate_restaurant_map(hotel, restaurants)

        return RestaurantSearchResponse(
            restaurants=restaurants, formatted=formatted, map_html=map_html
        )
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