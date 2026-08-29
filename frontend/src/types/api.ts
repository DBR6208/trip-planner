// Shared types matching backend API

export interface CityGuideReq {
  city: string;
  country: string;
}

export interface CityGuideRes {
  city_guide: string;
  tourist_office: string;
  tourist_office_data: TouristOfficeData | null;
  tourist_office_map: string;
}

export interface TouristOfficeData {
  name: string;
  address: string;
  place_id: string;
  latitude: number;
  longitude: number;
  website: string | null;
}

export interface Hotel {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  place_id: string;
  star_rating: string;
  review_rating: string | number;
  website: string | null;
  reviews_total: number;
  photo_url: string;
}

export interface HotelListRes {
  hotels: Hotel[];
  map_html: string;
}

export interface HotelMapReq {
  hotels: Hotel[];
  tourist_office: TouristOfficeData | null;
  selected_hotel_id: string | null;
}

export interface HotelMapRes {
  map_html: string;
}

export interface HotelDescReq {
  hotel: Hotel;
}

export interface HotelDescRes {
  description: string;
  formatted: string;
}

export interface Restaurant {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  place_id: string;
  rating: number;
  user_ratings_total: number;
  cuisine: string;
  website: string | null;
  walk_distance: string;
  walk_duration: string;
  distance_meters: number;
}

export interface RestaurantSearchReq {
  hotel_address: string;
  cuisines: string[];
}

export interface RestaurantSearchRes {
  restaurants: Restaurant[];
  formatted: string;
}

export interface ChargingStation {
  brand: string;
  latitude: number;
  longitude: number;
  location: string;
}

export interface RouteReq {
  start_address: string;
  end_address: string;
  start_battery: number;
}

export interface RouteRes {
  map_html: string;
  distance_km: number;
  arrival_battery: number;
  start_coords: [number, number] | null;
  end_coords: [number, number] | null;
  stations: ChargingStation[];
}

export interface PlanTripReq {
  start_address: string;
  end_address: string;
  start_battery: number;
  selected_stations_out: ChargingStation[];
  selected_stations_home: ChargingStation[];
}

export interface LegPlan {
  markdown: string;
  map_html: string;
  final_arrival_battery: number;
  total_distance: number;
}

export interface PlanTripRes {
  outbound: LegPlan;
  return: LegPlan;
}

export interface PlannerReq {
  city: string;
  hotel_name: string;
  hotel_address: string;
  restaurant_list: string;
  search_context: string;
}

export interface PlannerRes {
  itinerary: string;
}

export interface PDFReq {
  city: string;
  country: string;
  city_guide: string;
  tourist_office: string;
  hotel: string;
  restaurants: string;
  journey_out: string;
  journey_home: string;
  planner: string;
  cover_image?: string;
}

export interface PDFRes {
  pdf_path: string;
  download_url: string;
}

export const ALLOWED_CUISINES = [
  "Local",
  "Italian",
  "Croatian",
  "Grill",
  "Steakhouse",
  "Seafood",
] as const;

export type Cuisine = (typeof ALLOWED_CUISINES)[number];