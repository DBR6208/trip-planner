// API client for the backend

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  cityGuide: (city: string, country: string) =>
    request<import("../types/api").CityGuideRes>("/api/city-guide", {
      city,
      country,
    }),

  hotels: (city: string) =>
    request<import("../types/api").HotelListRes>("/api/hotels", { city }),

  hotelMap: (req: import("../types/api").HotelMapReq) =>
    request<import("../types/api").HotelMapRes>("/api/hotels/map", req),

  describeHotel: (hotel: import("../types/api").Hotel) =>
    request<import("../types/api").HotelDescRes>("/api/hotels/describe", {
      hotel,
    }),

  restaurants: (hotel_address: string, cuisines: string[], hotel: import("../types/api").Hotel | null) =>
    request<import("../types/api").RestaurantSearchRes>("/api/restaurants", {
      hotel_address,
      cuisines,
      hotel,
    }),

  route: (
    end_address: string,
    start_battery?: number,
    start_address?: string
  ) =>
    request<import("../types/api").RouteRes>("/api/route", {
      start_address,
      end_address,
      start_battery,
    }),

  planTrip: (req: import("../types/api").PlanTripReq) =>
    request<import("../types/api").PlanTripRes>("/api/route/plan", req),

  planner: (
    city: string,
    hotel_name: string,
    hotel_address: string,
    restaurant_list: string,
    search_context: string
  ) =>
    request<import("../types/api").PlannerRes>("/api/planner", {
      city,
      hotel_name,
      hotel_address,
      restaurant_list,
      search_context,
    }),

  generatePDF: (req: import("../types/api").PDFReq) =>
    request<import("../types/api").PDFRes>("/api/pdf", req),

  coverImages: (city: string, tourist_office_website?: string) =>
    request<import("../types/api").CoverImagesRes>("/api/cover-images", {
      city,
      tourist_office_website,
    }),

  /** Upload a user-selected cover image file; returns CoverImageInfo to add to gallery. */
  uploadCoverImage: async (file: File): Promise<import("../types/api").CoverImageInfo> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/api/cover-images/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },

  /** Download an image from a URL, save server-side, return CoverImageInfo. */
  addCoverImageFromUrl: (url: string, title?: string) =>
    request<import("../types/api").CoverImageInfo>("/api/cover-images/from-url", {
      url,
      title: title || "Web Image",
    }),

  /** Assemble brochure markdown from trip data (no PDF compilation). */
  brochureMarkdown: (req: import("../types/api").BrochureMarkdownReq) =>
    request<{ markdown: string }>("/api/brochure/markdown", req),

  /** Finalize PDF: copy from temp to guides/{City}.pdf and clear temp. */
  finalizePDF: (filename: string, city: string) =>
    request<{ download_url: string; filename: string }>("/api/pdf/finalize", {
      filename,
      city,
    }),
};