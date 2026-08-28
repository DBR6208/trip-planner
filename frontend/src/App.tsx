import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "./api/client";
import type {
  CityGuideRes,
  Hotel,
  Restaurant,
  ChargingStation,
  LegPlan,
} from "./types/api";
import {
  MapPin,
  Hotel as HotelIcon,
  Utensils,
  Car,
  FileText,
  Compass,
  CheckCircle2,
  ChevronRight,
  ChevronDown,
  Loader2,
  Download,
  Coffee,
  Sun,
} from "lucide-react";
import "./index.css";

// ── Markdown link component — open in new window ──
const markdownComponents = {
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

// ── Tab config ──
const TABS = [
  { id: 0, label: "Explore", icon: Compass },
  { id: 1, label: "Hotel", icon: HotelIcon },
  { id: 2, label: "Eateries", icon: Utensils },
  { id: 3, label: "Route", icon: Car },
  { id: 4, label: "Itinerary", icon: Coffee },
] as const;

type TabId = (typeof TABS)[number]["id"];

function tabReady(id: TabId, state: FullState): boolean {
  if (id === 0) return true;
  if (id === 1) return !!state.guideData;
  if (id === 2) return !!state.selectedHotel;
  if (id === 3) return state.restaurants.length > 0;
  if (id === 4) return !!state.selectedHotel;
  return false;
}

// ── Full state interface ──
interface FullState {
  city: string;
  country: string;
  guideData: CityGuideRes | null;
  guideLoading: boolean;
  hotels: Hotel[];
  selectedHotel: Hotel | null;
  hotelFormatted: string;
  hotelLoading: boolean;
  selectedCuisines: string[];
  restaurants: Restaurant[];
  restaurantFormatted: string;
  restaurantLoading: boolean;
  destCity: string;
  startBattery: number;
  routeMap: string;
  routeStations: ChargingStation[];
  routeInfo: string;
  routeLoading: boolean;
  selectedOut: ChargingStation[];
  selectedHome: ChargingStation[];
  planOut: LegPlan | null;
  planHome: LegPlan | null;
  planLoading: boolean;
  itinerary: string;
  itineraryLoading: boolean;
  pdfUrl: string;
  pdfLoading: boolean;
  error: string;
  showGuide: boolean;
}

// ── Main App ──
export default function App() {
  const [tab, setTab] = useState<TabId>(0);
  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // ── All state ──
  const [s, set] = useState<FullState>({
    city: "",
    country: "",
    guideData: null,
    guideLoading: false,
    hotels: [],
    selectedHotel: null,
    hotelFormatted: "",
    hotelLoading: false,
    selectedCuisines: ["Local", "Italian", "Croatian", "Grill", "Steakhouse", "Seafood"],
    restaurants: [],
    restaurantFormatted: "",
    restaurantLoading: false,
    destCity: "",
    startBattery: 90,
    routeMap: "",
    routeStations: [],
    routeInfo: "",
    routeLoading: false,
    selectedOut: [],
    selectedHome: [],
    planOut: null,
    planHome: null,
    planLoading: false,
    itinerary: "",
    itineraryLoading: false,
    pdfUrl: "",
    pdfLoading: false,
    error: "",
    showGuide: false,
  });
  const [sidebarOpen] = useState(true);

  const update = useCallback(<K extends keyof FullState>(key: K, val: FullState[K]) => {
    set((prev) => ({ ...prev, [key]: val }));
  }, []);

  const showError = useCallback((e: unknown) => {
    const msg = e instanceof Error ? e.message : String(e);
    set((prev) => ({ ...prev, error: msg }));
  }, []);

  const dismissError = useCallback(() => {
    set((prev) => ({ ...prev, error: "" }));
  }, []);

  const ready = (id: TabId) => tabReady(id, s);

  // ── Handlers ──
  const handleCityGuide = async () => {
    if (!s.city.trim()) return;
    update("guideLoading", true);
    update("error", "");
    try {
      const data = await api.cityGuide(s.city.trim(), s.country.trim() || "Germany");
      update("guideData", data);
      update("showGuide", true);
    } catch (e) { showError(e); }
    finally { update("guideLoading", false); }
  };

  const handleSearchHotels = async () => {
    update("hotelLoading", true);
    update("error", "");
    try {
      const data = await api.hotels(s.city.trim());
      update("hotels", data.hotels);
      if (data.hotels.length === 0) update("error", "No 4–5 star hotels found in city center.");
    } catch (e) { showError(e); }
    finally { update("hotelLoading", false); }
  };

  const handleSelectHotel = async (h: Hotel) => {
    update("selectedHotel", h);
    update("hotelLoading", true);
    update("error", "");
    try {
      const data = await api.describeHotel(h);
      update("hotelFormatted", data.formatted);
    } catch (e) { showError(e); }
    finally { update("hotelLoading", false); }
  };

  const toggleCuisine = (c: string) => {
    set((prev) => ({
      ...prev,
      selectedCuisines: prev.selectedCuisines.includes(c)
        ? prev.selectedCuisines.filter((x) => x !== c)
        : [...prev.selectedCuisines, c],
    }));
  };

  const handleSearchRestaurants = async () => {
    if (!s.selectedHotel) return;
    update("restaurantLoading", true);
    update("error", "");
    try {
      const data = await api.restaurants(
        s.selectedHotel.address,
        s.selectedCuisines.length > 0 ? s.selectedCuisines : ["Local"]
      );
      update("restaurants", data.restaurants);
      update("restaurantFormatted", data.formatted);
    } catch (e) { showError(e); }
    finally { update("restaurantLoading", false); }
  };

  const handleFindRoute = async () => {
    if (!s.destCity.trim()) return;
    update("routeLoading", true);
    update("error", "");
    try {
      const data = await api.route(s.destCity.trim(), s.startBattery);
      update("routeMap", data.map_html);
      update("routeStations", data.stations);
      update("routeInfo", `Distance: ${data.distance_km} km · Arrival: ${data.arrival_battery}% · ${data.stations.length} stations`);
      update("selectedOut", []);
      update("selectedHome", []);
      update("planOut", null);
      update("planHome", null);
    } catch (e) { showError(e); }
    finally { update("routeLoading", false); }
  };

  const handlePlanTrip = async () => {
    if (s.selectedOut.length === 0) {
      update("error", "Select at least one charging stop for the way out.");
      return;
    }
    update("planLoading", true);
    update("error", "");
    try {
      const data = await api.planTrip({
        start_address: "Heirweg 85A, 9190 Stekene, Belgium",
        end_address: s.destCity.trim(),
        start_battery: s.startBattery,
        selected_stations_out: s.selectedOut,
        selected_stations_home: s.selectedHome.length > 0 ? s.selectedHome : [],
      });
      update("planOut", data.outbound);
      update("planHome", data.return);
    } catch (e) { showError(e); }
    finally { update("planLoading", false); }
  };

  const handleGenerateItinerary = async () => {
    if (!s.selectedHotel || !s.restaurantFormatted) return;
    update("itineraryLoading", true);
    update("error", "");
    try {
      const data = await api.planner(
        s.city,
        s.selectedHotel.name,
        s.selectedHotel.address,
        s.restaurantFormatted,
        s.guideData?.city_guide || ""
      );
      update("itinerary", data.itinerary);
    } catch (e) { showError(e); }
    finally { update("itineraryLoading", false); }
  };

  const handleGeneratePDF = async () => {
    if (!s.guideData || !s.selectedHotel) return;
    update("pdfLoading", true);
    update("error", "");
    try {
      const data = await api.generatePDF({
        city: s.city,
        country: s.country || "Germany",
        city_guide: s.guideData.city_guide,
        tourist_office: s.guideData.tourist_office,
        hotel: s.hotelFormatted,
        restaurants: s.restaurantFormatted,
        journey_out: s.planOut?.markdown || "",
        journey_home: s.planHome?.markdown || "",
        planner: s.itinerary,
      });
      update("pdfUrl", data.download_url);
    } catch (e) { showError(e); }
    finally { update("pdfLoading", false); }
  };

  // ── Render ──
  return (
    <div className="gradio-container">
      {/* ── Header — big centered title like Gradio's gr.Markdown("<h1>") ── */}
      <header className="mb-1 text-center">
        <h1 className="text-2xl font-bold text-brand-blue tracking-tight">
          Weekend Trip Planner
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          DBG Travel · Weekend Travel Guide Generator
        </p>
        {s.pdfUrl && (
          <a
            href={`${apiBase}${s.pdfUrl}`}
            className="btn btn-primary btn-sm gap-1.5 mt-2"
            target="_blank"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </a>
        )}
      </header>

      {/* ── Tab Bar — Gradio Tabs ── */}
      <div className="tabs tabs-bordered mb-4 mt-3" role="tablist">
        {TABS.map((t) => {
          const isReady = ready(t.id);
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              role="tab"
              className={`tab gap-1.5 font-medium ${
                tab === t.id ? "tab-active" : isReady ? "text-gray-600" : "text-gray-400"
              }`}
              onClick={() => setTab(t.id)}
            >
              <Icon className={`w-4 h-4 ${tab === t.id ? "text-brand-blue" : isReady ? "text-gray-500" : "text-gray-400"}`} />
              {t.label}
              {isReady && tab !== t.id && (
                <CheckCircle2 className="w-3 h-3 text-green-500 ml-0.5" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Error ── */}
      {s.error && (
        <div className="error-banner mb-4">
          <span className="flex-1">{s.error}</span>
          <button onClick={dismissError} className="text-red-800 hover:text-red-950 font-bold leading-none text-lg">&times;</button>
        </div>
      )}

      {/* ════════════════ TAB 0: EXPLORE ════════════════ */}
      {tab === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-5">
          {/* Sidebar */}
          <div className={`panel p-4 ${sidebarOpen ? "" : "hidden"} md:block`}>
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <Compass className="w-4 h-4" />
              Destination
            </h2>
            <fieldset className="fieldset gap-2">
              <input
                type="text"
                placeholder="City (e.g. Aachen)"
                value={s.city}
                onChange={(e) => update("city", e.target.value)}
                className="input w-full text-sm"
              />
              <input
                type="text"
                placeholder="Country (default: Germany)"
                value={s.country}
                onChange={(e) => update("country", e.target.value)}
                className="input w-full text-sm"
              />
              <button
                onClick={handleCityGuide}
                disabled={!s.city.trim() || s.guideLoading}
                className="btn btn-primary mt-1"
              >
                {s.guideLoading ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Researching…
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <Compass className="w-4 h-4" />
                    Explore City
                  </span>
                )}
              </button>
            </fieldset>
          </div>

          {/* Output */}
          <div className="space-y-4">
            {!s.guideData ? (
              <div className="panel p-8 text-center">
                {/* Map pin SVG */}
                <svg className="w-16 h-16 mx-auto mb-4 text-brand-blue/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="currentColor" fillOpacity="0.08"/>
                  <circle cx="12" cy="9" r="2.5" fill="currentColor" fillOpacity="0.2"/>
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-12 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Start Here</span>
                  <div className="h-px w-12 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Plan Your Weekend Escape</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto mb-5 leading-relaxed">
                  Enter a city in the sidebar to generate a curated travel guide with local insights,
                  hidden gems, and the best places to eat, stay, and explore.
                </p>
                <div className="flex items-center justify-center gap-6 text-xs text-gray-400">
                  <div className="flex flex-col items-center gap-1">
                    <svg className="w-5 h-5 text-brand-gold/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
                    </svg>
                    <span>Research city</span>
                  </div>
                  <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <svg className="w-5 h-5 text-brand-gold/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5V3.545M12.75 21h7.5V10.75M2.25 21h1.5m18 0h-18M2.25 9l4.5-1.636M18.75 3l-1.5.545m0 6.205l3 1m1.5.5l-1.5-.5M6.75 7.364V3h-3v18m3-13.636l10.5-3.819"/>
                    </svg>
                    <span>Pick hotel</span>
                  </div>
                  <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <svg className="w-5 h-5 text-brand-gold/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z"/>
                    </svg>
                    <span>Find restaurants</span>
                  </div>
                  <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <svg className="w-5 h-5 text-brand-gold/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
                    </svg>
                    <span>Generate PDF</span>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="panel p-4">
                  <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                    <MapPin className="w-4 h-4" />
                    City Guide — {s.city}
                  </h2>
                  <div className="scroll-content pr-1">
                    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.guideData.city_guide}</ReactMarkdown></div>
                  </div>
                </div>
                {s.guideData.tourist_office && (
                  <div className="panel p-4">
                    <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                      Info
                      Tourist Office
                    </h2>
                    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.guideData.tourist_office}</ReactMarkdown></div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ TAB 1: HOTEL ════════════════ */}
      {tab === 1 && (
        <div className="flex flex-row gap-5" style={{ minHeight: '60vh' }}>
          {/* Sidebar */}
          <div className="w-[260px] flex-shrink-0">
            <div className="panel p-4">
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <HotelIcon className="w-4 h-4" />
              Select Hotel
            </h2>
            {!s.guideData ? (
              <p className="text-xs text-gray-400">Generate a city guide first.</p>
            ) : (
              <>
                {s.hotels.length === 0 && !s.hotelLoading && (
                  <button onClick={handleSearchHotels} className="btn btn-primary btn-sm w-full">
                    Search 4–5 Star Hotels
                  </button>
                )}
                {s.hotelLoading && (
                  <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Searching…
                  </div>
                )}
                {s.hotels.length > 0 && (
                  <div className="space-y-2 max-h-[420px] overflow-y-auto">
                    {s.hotels.map((h, i) => {
                      const starNum = parseInt(h.star_rating, 10) || 0;
                      const stars = "★".repeat(starNum) + "☆".repeat(Math.max(0, 5 - starNum));
                      return (
                        <label
                          key={i}
                          className={`block p-2.5 rounded-lg border cursor-pointer transition-all text-sm ${
                            s.selectedHotel?.place_id === h.place_id
                              ? "border-brand-blue bg-blue-50/60"
                              : "border-base-300 hover:border-gray-400"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <input
                              type="radio"
                              name="hotel-select"
                              checked={s.selectedHotel?.place_id === h.place_id}
                              onChange={() => handleSelectHotel(h)}
                              className="radio radio-sm"
                            />
                            <span className="font-medium text-sm leading-tight">{h.name}</span>
                          </div>
                          <div className="text-xs ml-8 mt-1 flex items-center gap-2 text-gray-600">
                            <span className="text-amber-500 tracking-wide">{stars}</span>
                            <span>{h.review_rating}</span>
                            <span className="text-gray-400">({h.reviews_total} reviews)</span>
                          </div>
                          <div className="text-xs text-gray-400 truncate ml-8 mt-0.5">{h.address}</div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
          </div>

          {/* Output */}
          <div className="flex-1 min-w-0 space-y-4">
            {!s.selectedHotel ? (
              <div className="panel p-8 text-center">
                <svg className="w-14 h-14 mx-auto mb-4 text-brand-blue/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 2</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Find Your Hotel</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Generate a city guide first in the Explore tab, then search for 4–5 star hotels in the city center here.
                </p>
              </div>
            ) : (
              <div className="panel p-4">
                <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                  <HotelIcon className="w-4 h-4" />
                  {s.selectedHotel.name}
                </h2>
                {s.hotelFormatted && (
                  <div className="scroll-content pr-1">
                    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.hotelFormatted}</ReactMarkdown></div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ TAB 2: EATERIES ════════════════ */}
      {tab === 2 && (
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-5">
          {/* Sidebar */}
          <div className={`panel p-4 ${sidebarOpen ? "" : "hidden"} md:block`}>
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <Utensils className="w-4 h-4" />
              Cuisine Selection
            </h2>
            {!s.selectedHotel ? (
              <p className="text-xs text-gray-400">Select a hotel first.</p>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-2">Choose cuisines for the brochure.</p>
                <div className="space-y-1.5 mb-3">
                  {["Local", "Italian", "Croatian", "Grill", "Steakhouse", "Seafood"].map((c) => (
                    <label
                      key={c}
                      className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border cursor-pointer text-sm ${
                        s.selectedCuisines.includes(c)
                          ? "border-brand-blue bg-blue-50/60"
                          : "border-base-300 hover:border-gray-400"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={s.selectedCuisines.includes(c)}
                        onChange={() => toggleCuisine(c)}
                        className="checkbox checkbox-sm"
                      />
                      <span>{c}</span>
                    </label>
                  ))}
                </div>
                <button
                  onClick={handleSearchRestaurants}
                  disabled={s.restaurantLoading}
                  className="btn btn-primary btn-sm w-full"
                >
                  {s.restaurantLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Searching…
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <Utensils className="w-4 h-4" />
                      Find Restaurants
                    </span>
                  )}
                </button>
                {s.restaurants.length > 0 && (
                  <p className="text-xs text-green-600 mt-2 font-medium">
                    {s.restaurants.length} restaurants found
                  </p>
                )}
              </>
            )}
          </div>

          {/* Output */}
          <div className="space-y-4">
            {!s.restaurantFormatted ? (
              <div className="panel p-8 text-center">
                <svg className="w-14 h-14 mx-auto mb-4 text-brand-blue/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.871c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513M15 18.75A3.75 3.75 0 0018 15v-1.394c0-1.297-1.013-2.358-2.302-2.394a43.425 43.425 0 00-7.396 0C7.013 11.248 6 12.309 6 13.606V15a3.75 3.75 0 003 3.75m0 0v2.25m0-2.25h6m-6 0H9"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 3</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Select Your Cuisines</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Choose from Local, Italian, Croatian, Grill, Steakhouse, and Seafood — then search for the best restaurants near your hotel.
                </p>
              </div>
            ) : (
              <div className="panel p-4">
                <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                  <Utensils className="w-4 h-4" />
                  Restaurant Selection
                </h2>
                <div className="scroll-content pr-1">
                  <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.restaurantFormatted}</ReactMarkdown></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ TAB 3: ROUTE ════════════════ */}
      {tab === 3 && (
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-5">
          {/* Sidebar */}
          <div className={`panel p-4 ${sidebarOpen ? "" : "hidden"} md:block`}>
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <Car className="w-4 h-4" />
              EV Route Planning
            </h2>
            {s.restaurants.length === 0 ? (
              <p className="text-xs text-gray-400">Complete restaurant search first.</p>
            ) : (
              <>
                <fieldset className="fieldset gap-2">
                  <input
                    type="text"
                    placeholder="Destination city"
                    value={s.destCity}
                    onChange={(e) => update("destCity", e.target.value)}
                    className="input w-full text-sm"
                  />
                  <label className="flex items-center gap-2 text-xs text-gray-600">
                    Battery %
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={s.startBattery}
                      onChange={(e) => update("startBattery", Number(e.target.value))}
                      className="range range-sm flex-1"
                    />
                    <span className="font-mono w-8 text-right">{s.startBattery}%</span>
                  </label>
                  <button
                    onClick={handleFindRoute}
                    disabled={!s.destCity.trim() || s.routeLoading}
                    className="btn btn-primary btn-sm mt-1"
                  >
                    {s.routeLoading ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Calculating…
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5">
                        <Car className="w-4 h-4" />
                        Find Route
                      </span>
                    )}
                  </button>
                </fieldset>

                {s.routeInfo && (
                  <p className="text-xs text-gray-600 mt-2 font-medium">{s.routeInfo}</p>
                )}

                {/* Station selectors */}
                {s.routeStations.length > 0 && (
                  <>
                    <hr className="my-3 border-base-300" />
                    <p className="text-xs font-medium text-gray-600 mb-1.5">Way Out Stops</p>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {s.routeStations.map((st, i) => (
                        <button
                          key={i}
                          onClick={() =>
                            set((prev) => ({
                              ...prev,
                              selectedOut: prev.selectedOut.find((x) => x.location === st.location)
                                ? prev.selectedOut.filter((x) => x.location !== st.location)
                                : [...prev.selectedOut, st],
                            }))
                          }
                          className={`btn btn-xs ${
                            s.selectedOut.find((x) => x.location === st.location)
                              ? "btn-primary"
                              : "btn-outline"
                          }`}
                        >
                          {st.brand}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs font-medium text-gray-600 mb-1.5">
                      Return Stops{" "}
                      <span className="text-gray-400 font-normal">(optional)</span>
                    </p>
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {s.routeStations.map((st, i) => (
                        <button
                          key={i}
                          onClick={() =>
                            set((prev) => ({
                              ...prev,
                              selectedHome: prev.selectedHome.find((x) => x.location === st.location)
                                ? prev.selectedHome.filter((x) => x.location !== st.location)
                                : [...prev.selectedHome, st],
                            }))
                          }
                          className={`btn btn-xs ${
                            s.selectedHome.find((x) => x.location === st.location)
                              ? "btn-success"
                              : "btn-outline"
                          }`}
                        >
                          {st.brand}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={handlePlanTrip}
                      disabled={s.selectedOut.length === 0 || s.planLoading}
                      className="btn btn-primary btn-sm w-full"
                    >
                      {s.planLoading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Planning…
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <Car className="w-4 h-4" />
                          Plan Trip
                        </span>
                      )}
                    </button>
                  </>
                )}
              </>
            )}
          </div>

          {/* Output */}
          <div className="space-y-4">
            {!s.routeMap ? (
              <div className="panel p-8 text-center">
                <svg className="w-14 h-14 mx-auto mb-4 text-brand-blue/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 4</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Plan Your EV Route</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Enter your destination city and battery percentage. The route planner calculates the journey including charging stops along the way.
                </p>
              </div>
            ) : (
              <>
                <div className="panel p-3">
                  <h3 className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" />
                    Route Overview
                  </h3>
                  <div
                    className="map-container"
                    dangerouslySetInnerHTML={{ __html: s.routeMap }}
                  />
                </div>
                {s.planOut && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="panel p-3">
                      <h3 className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                        <ChevronRight className="w-3.5 h-3.5 text-brand-blue" />
                        Way Out
                      </h3>
                      <div
                        className="map-container mb-2"
                        dangerouslySetInnerHTML={{ __html: s.planOut.map_html }}
                      />
                      <div className="markdown text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.planOut.markdown}</ReactMarkdown></div>
                    </div>
                    <div className="panel p-3">
                      <h3 className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                        <ChevronDown className="w-3.5 h-3.5 text-brand-blue" />
                        Way Home
                      </h3>
                      <div
                        className="map-container mb-2"
                        dangerouslySetInnerHTML={{ __html: s.planHome?.map_html || "" }}
                      />
                      <div className="markdown text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.planHome?.markdown || ""}</ReactMarkdown></div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ TAB 4: ITINERARY ════════════════ */}
      {tab === 4 && (
        <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-5">
          {/* Sidebar */}
          <div className={`panel p-4 ${sidebarOpen ? "" : "hidden"} md:block`}>
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <FileText className="w-4 h-4" />
              Itinerary & PDF
            </h2>

            {!s.selectedHotel ? (
              <p className="text-xs text-gray-400">Select a hotel first.</p>
            ) : (
              <div className="space-y-3">
                <div>
                  <h3 className="text-xs font-medium text-gray-600 mb-1">Generate</h3>
                  <button
                    onClick={handleGenerateItinerary}
                    disabled={s.itineraryLoading || !s.restaurantFormatted}
                    className="btn btn-primary btn-sm w-full"
                  >
                    {s.itineraryLoading ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating…
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5">
                        <Sun className="w-4 h-4" />
                        Weekend Itinerary
                      </span>
                    )}
                  </button>
                </div>

                {s.itinerary && (
                  <div>
                    <h3 className="text-xs font-medium text-gray-600 mb-1">PDF</h3>
                    <button
                      onClick={handleGeneratePDF}
                      disabled={s.pdfLoading}
                      className="btn btn-primary btn-sm w-full"
                    >
                      {s.pdfLoading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Generating…
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <FileText className="w-4 h-4" />
                          Generate PDF
                        </span>
                      )}
                    </button>
                  </div>
                )}

                {s.pdfUrl && (
                  <div className="p-2.5 rounded-lg bg-green-50 border border-green-200">
                    <p className="text-xs text-green-700 font-medium flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      PDF ready!
                    </p>
                    <a
                      href={`${apiBase}${s.pdfUrl}`}
                      target="_blank"
                      className="text-xs text-brand-blue underline mt-0.5 inline-block"
                    >
                      Download Here
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Output */}
          <div className="space-y-4">
            {!s.itinerary ? (
              <div className="panel p-8 text-center">
                <svg className="w-14 h-14 mx-auto mb-4 text-brand-blue/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 5</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Generate Your Itinerary</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Once you have a hotel and restaurant selections, generate a full weekend itinerary — then export it as a polished PDF brochure.
                </p>
              </div>
            ) : (
              <div className="panel p-4">
                <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                  <Sun className="w-4 h-4" />
                  Weekend Itinerary — {s.city}
                </h2>
                <div className="scroll-content pr-1">
                  <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.itinerary}</ReactMarkdown></div>
                </div>
              </div>
            )}

            {/* Planned journey */}
            {s.planOut && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="panel p-3">
                  <h3 className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                    <ChevronRight className="w-3.5 h-3.5 text-brand-blue" />
                    Way Out
                  </h3>
                  <div className="markdown text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.planOut.markdown}</ReactMarkdown></div>
                </div>
                <div className="panel p-3">
                  <h3 className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                    <ChevronDown className="w-3.5 h-3.5 text-brand-blue" />
                    Way Home
                  </h3>
                  <div className="markdown text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.planHome?.markdown || ""}</ReactMarkdown></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Footer ── */}
      <footer className="mt-10 text-center text-xs text-gray-400 pb-6">
        DBG Travel · Generated by Trip Planner
      </footer>
    </div>
  );
}