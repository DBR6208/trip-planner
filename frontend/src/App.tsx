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
  Calendar,
  Sun,
  Image,
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

function cap(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

// ── Tab config ──
const TABS = [
  { id: 0, label: "Explore", icon: Compass },
  { id: 1, label: "Hotel", icon: HotelIcon },
  { id: 2, label: "Restaurants", icon: Utensils },
  { id: 3, label: "Route", icon: Car },
  { id: 4, label: "Planning", icon: Calendar },
  { id: 5, label: "Brochure", icon: FileText },
] as const;

type TabId = (typeof TABS)[number]["id"];

function tabReady(id: TabId, state: FullState): boolean {
  if (id === 0) return true;
  if (id === 1) return !!state.guideData;
  if (id === 2) return !!state.selectedHotel;
  if (id === 3) return !!state.selectedHotel;
  if (id === 4) return !!state.selectedHotel;
  if (id === 5) return !!state.guideData && !!state.selectedHotel && !!state.itinerary;
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
  hotelMapHtml: string;
  selectedCuisines: string[];
  restaurants: Restaurant[];
  restaurantFormatted: string;
  restaurantMapHtml: string;
  restaurantLoading: boolean;
  destAddress: string;
  startAddress: string;
  startAddressPreset: number;
  startAddressCustom: string;
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
  coverImages: import("./types/api").CoverImageInfo[];
  coverImagesLoading: boolean;
  selectedCoverImage: import("./types/api").CoverImageInfo | null;
  error: string;
  showGuide: boolean;
}

// ── Cuisine colors (matching backend) ──
const CUI_COLORS: Record<string, string> = {
  Local: "#2E7D32",
  Italian: "#C62828",
  Croatian: "#1565C0",
  Grill: "#E65100",
  Steakhouse: "#6A1B9A",
  Seafood: "#00838F",
};

// ── Start address presets ──
const START_ADDRESSES = [
  "Leuvensesteenweg 431, 2812 Mechelen",
  "Heirweg 85A, 9190 Stekene, Belgium",
  "Regentiestraat 41D, 9190 Stekene",
];

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
    hotelMapHtml: "",
    selectedCuisines: [],
    restaurants: [],
    restaurantFormatted: "",
    restaurantMapHtml: "",
    restaurantLoading: false,
    destAddress: "",
    startAddress: START_ADDRESSES[0],
    startAddressPreset: 0,
    startAddressCustom: "",
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
    coverImages: [],
    coverImagesLoading: false,
    selectedCoverImage: null,
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
      update("hotelMapHtml", data.map_html || "");
      if (data.hotels.length === 0) update("error", "No 4–5 star hotels found in city center.");
    } catch (e) { showError(e); }
    finally { update("hotelLoading", false); }
  };

  const handleSelectHotel = async (h: Hotel) => {
    update("selectedHotel", h);
    update("hotelLoading", true);
    update("hotelFormatted", "");
    update("destAddress", h.address);
    update("error", "");
    try {
      // Fire map update and LLM description in PARALLEL
      // Map regenerates instantly (just marker colors + parking fetch)
      // Description takes 5-10s (Tavily search + LLM)
      const mapPromise = s.guideData?.tourist_office_data
        ? api.hotelMap({
            hotels: s.hotels,
            tourist_office: s.guideData.tourist_office_data,
            selected_hotel_id: h.place_id,
          }).then((mapData) => update("hotelMapHtml", mapData.map_html))
        : Promise.resolve();

      const [data] = await Promise.all([
        api.describeHotel(h),
        mapPromise,
      ]);
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
    update("restaurantFormatted", "");
    update("restaurantMapHtml", "");
    update("error", "");
    try {
      const data = await api.restaurants(
        s.selectedHotel.address,
        s.selectedCuisines,
        s.selectedHotel,
      );
      update("restaurants", data.restaurants);
      update("restaurantFormatted", data.formatted);
      update("restaurantMapHtml", data.map_html);
    } catch (e) { showError(e); }
    finally { update("restaurantLoading", false); }
  };

  const handleFindRoute = async () => {
    if (!s.destAddress.trim()) return;
    update("routeLoading", true);
    update("routeMap", "");
    update("routeStations", []);
    update("selectedOut", []);
    update("selectedHome", []);
    update("planOut", null);
    update("planHome", null);
    update("error", "");
    try {
      const data = await api.route(s.destAddress.trim(), s.startBattery, s.startAddress);
      update("routeMap", data.map_html);
      update("routeStations", data.stations);
      update("selectedOut", data.recommended_out);
      update("selectedHome", data.recommended_home);
      update("routeInfo", `Distance: ${data.distance_km} km · Arrival: ${data.arrival_battery}% · ${data.stations.length} stations`);
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
        start_address: s.startAddress,
        end_address: s.destAddress,
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
        [
          s.guideData?.city_guide || "",
          s.guideData?.tourist_office || "",
        ].filter(Boolean).join("\n\n"),
      );
      update("itinerary", data.itinerary);
    } catch (e) { showError(e); }
    finally { update("itineraryLoading", false); }
  };

  const handleFindCoverImages = async () => {
    if (!s.city.trim()) return;
    update("coverImagesLoading", true);
    update("coverImages", []);
    update("selectedCoverImage", null);
    update("error", "");
    try {
      const data = await api.coverImages(
        s.city,
        s.guideData?.tourist_office_data?.website ?? undefined,
      );
      update("coverImages", data.images);
    } catch (e) { showError(e); }
    finally { update("coverImagesLoading", false); }
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
        cover_image: s.selectedCoverImage?.url,
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
                <div className="flex items-center justify-center gap-4 text-xs text-gray-400">
                  <div className="flex flex-col items-center gap-1">
                    <Compass className="w-5 h-5 text-brand-gold/60" />
                    <span>Explore</span>
                  </div>
                  <svg className="w-3.5 h-3.5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <HotelIcon className="w-5 h-5 text-brand-gold/60" />
                    <span>Hotel</span>
                  </div>
                  <svg className="w-3.5 h-3.5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <Utensils className="w-5 h-5 text-brand-gold/60" />
                    <span>Restaurants</span>
                  </div>
                  <svg className="w-3.5 h-3.5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <Car className="w-5 h-5 text-brand-gold/60" />
                    <span>Route</span>
                  </div>
                  <svg className="w-3.5 h-3.5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <Calendar className="w-5 h-5 text-brand-gold/60" />
                    <span>Planning</span>
                  </div>
                  <svg className="w-3.5 h-3.5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/>
                  </svg>
                  <div className="flex flex-col items-center gap-1">
                    <FileText className="w-5 h-5 text-brand-gold/60" />
                    <span>Brochure</span>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="panel p-4">
                  <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                    <MapPin className="w-4 h-4" />
                    City Guide — {cap(s.city)}
                  </h2>
                  <div className="scroll-content pr-1">
                    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.guideData.city_guide}</ReactMarkdown></div>
                  </div>
                </div>
                {s.guideData.tourist_office && (
                  <div className="panel p-4">
                    <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                      <MapPin className="w-4 h-4" />
                      Tourist Office
                    </h2>
                    <div className="markdown mb-3"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.guideData.tourist_office}</ReactMarkdown></div>
                    {s.guideData.tourist_office_map && (
                      <div className="rounded-lg overflow-hidden border border-gray-200">
                        <iframe
                          srcDoc={s.guideData.tourist_office_map}
                          title="Tourist Office Map"
                          className="w-full"
                          style={{ height: "600px", border: "none", overflow: "hidden" }}
                          scrolling="no"
                          sandbox="allow-scripts allow-popups allow-same-origin"
                        />
                      </div>
                    )}
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
                {s.hotels.length === 0 && s.hotelLoading && (
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
            {s.hotelLoading && !s.hotelMapHtml && (
              <div className="panel p-8 text-center">
                <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-brand-blue/50" />
                <p className="text-sm text-gray-500">Searching for hotels…</p>
              </div>
            )}
            {s.hotelMapHtml && (
              <div className="panel p-0 overflow-hidden rounded-xl border border-gray-200">
                <iframe
                  srcDoc={s.hotelMapHtml}
                  title="Hotel Map"
                  className="w-full"
                  style={{ height: "600px", border: "none", overflow: "hidden" }}
                  scrolling="no"
                  sandbox="allow-scripts allow-popups allow-same-origin"
                />
              </div>
            )}
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
                <div className="flex flex-row gap-4">
                  {s.selectedHotel.photo_url && (
                    <div className="w-[18rem] h-[13.5rem] flex-shrink-0 rounded-lg overflow-hidden border border-gray-200">
                      <img
                        src={s.selectedHotel.photo_url}
                        alt={s.selectedHotel.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                      <HotelIcon className="w-4 h-4" />
                      {s.selectedHotel.name}
                    </h2>
                    {s.hotelLoading ? (
                      <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating hotel description…
                      </div>
                    ) : s.hotelFormatted ? (
                      <div className="scroll-content pr-1">
                        <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.hotelFormatted}</ReactMarkdown></div>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400">Select a hotel to see details.</p>
                    )}
                  </div>
                </div>
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
                <p className="text-xs text-gray-500 mb-2">Select cuisines to search for. Leave empty to search all.</p>
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
                      <span className="w-2.5 h-2.5 rounded-full inline-block flex-shrink-0" style={{ backgroundColor: CUI_COLORS[c] }} />
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
            {s.restaurantLoading && !s.restaurantMapHtml && (
              <div className="panel p-8 text-center">
                <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-brand-blue/50" />
                <p className="text-sm text-gray-500">Searching for restaurants…</p>
              </div>
            )}
            {s.restaurantMapHtml && (
              <div className="panel p-0 overflow-hidden rounded-xl border border-gray-200">
                <iframe
                  srcDoc={s.restaurantMapHtml}
                  title="Restaurant Map"
                  className="w-full"
                  style={{ height: "600px", border: "none", overflow: "hidden" }}
                  scrolling="no"
                  sandbox="allow-scripts allow-popups allow-same-origin"
                />
              </div>
            )}
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
              <>
                <div className="panel p-4">
                  <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                    <Utensils className="w-4 h-4" />
                    Restaurant Selection
                  </h2>
                  <div className="scroll-content pr-1">
                    <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.restaurantFormatted}</ReactMarkdown></div>
                  </div>
                </div>
              </>
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
            {!s.selectedHotel ? (
              <p className="text-xs text-gray-400">Select a hotel for the destination.</p>
            ) : (
              <>
                <fieldset className="fieldset gap-2">
                  <label className="text-xs font-medium text-gray-600">Starting from</label>
                  {START_ADDRESSES.map((addr, i) => (
                    <label
                      key={i}
                      className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-pointer text-xs ${
                        s.startAddressPreset === i
                          ? "border-brand-blue bg-blue-50/60"
                          : "border-base-300 hover:border-gray-400"
                      }`}
                    >
                      <input
                        type="radio"
                        name="start-address"
                        checked={s.startAddressPreset === i}
                        onChange={() => {
                          set((prev) => ({
                            ...prev,
                            startAddressPreset: i,
                            startAddress: addr,
                            startAddressCustom: "",
                          }));
                        }}
                        className="radio radio-sm"
                      />
                      <span className="truncate">{addr.split(",")[0]}</span>
                    </label>
                  ))}
                  <label
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-pointer text-xs ${
                      s.startAddressPreset === -1
                        ? "border-brand-blue bg-blue-50/60"
                        : "border-base-300 hover:border-gray-400"
                    }`}
                  >
                    <input
                      type="radio"
                      name="start-address"
                      checked={s.startAddressPreset === -1}
                      onChange={() => {
                        set((prev) => ({
                          ...prev,
                          startAddressPreset: -1,
                          startAddress: prev.startAddressCustom,
                        }));
                      }}
                      className="radio radio-sm"
                    />
                    <span>Other…</span>
                  </label>
                  {s.startAddressPreset === -1 && (
                    <input
                      type="text"
                      placeholder="Enter start address"
                      value={s.startAddressCustom}
                      onChange={(e) => {
                        const v = e.target.value;
                        set((prev) => ({
                          ...prev,
                          startAddressCustom: v,
                          startAddress: v,
                        }));
                      }}
                      className="input w-full text-sm"
                    />
                  )}
                  <hr className="my-1 border-base-300" />
                  <label className="text-xs font-medium text-gray-600">Destination</label>
                  <div className="text-xs text-gray-700 bg-gray-50 rounded-lg px-2.5 py-2 border border-gray-200 truncate">
                    {s.destAddress || "Select a hotel first"}
                  </div>
                  <label className="flex items-center gap-2 text-xs text-gray-600 mt-1">
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
                    disabled={!s.destAddress.trim() || !s.startAddress.trim() || s.routeLoading}
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

                {/* Station selectors — checkbox per direction */}
                {s.routeStations.length > 0 && (
                  <>
                    <hr className="my-3 border-base-300" />
                    <p className="text-xs font-medium text-gray-600 mb-2">
                      Charging Stations
                    </p>
                    <div className="space-y-1.5 max-h-[320px] overflow-y-auto">
                      {s.routeStations.map((st, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-1.5 px-2 py-1.5 rounded-lg border border-base-300 text-xs"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-700 truncate">
                              {st.brand}
                            </div>
                            <div className="text-gray-400 truncate">
                              {st.location}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
                            <label className="flex items-center gap-1 cursor-pointer">
                              <input
                                type="checkbox"
                                className="checkbox checkbox-xs"
                                checked={!!s.selectedOut.find((x) => x.location === st.location)}
                                onChange={() =>
                                  set((prev) => ({
                                    ...prev,
                                    selectedOut: prev.selectedOut.find((x) => x.location === st.location)
                                      ? prev.selectedOut.filter((x) => x.location !== st.location)
                                      : [...prev.selectedOut, st],
                                  }))
                                }
                              />
                              <span className="text-[11px] text-brand-blue">Out</span>
                            </label>
                            <label className="flex items-center gap-1 cursor-pointer">
                              <input
                                type="checkbox"
                                className="checkbox checkbox-xs"
                                checked={!!s.selectedHome.find((x) => x.location === st.location)}
                                onChange={() =>
                                  set((prev) => ({
                                    ...prev,
                                    selectedHome: prev.selectedHome.find((x) => x.location === st.location)
                                      ? prev.selectedHome.filter((x) => x.location !== st.location)
                                      : [...prev.selectedHome, st],
                                  }))
                                }
                              />
                              <span className="text-[11px] text-gray-500">Home</span>
                            </label>
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={handlePlanTrip}
                      disabled={s.selectedOut.length === 0 || s.planLoading}
                      className="btn btn-primary btn-sm w-full mt-2"
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
                  Enter your start address and destination. The route planner calculates the journey including charging stops along the way.
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
                        className="map-container-sm mb-2"
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
                        className="map-container-sm mb-2"
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
              Planning
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
                        Weekend Planning
                      </span>
                    )}
                  </button>
                </div>
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
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Generate Your Weekend Plan</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Once you have a hotel and restaurant selections, generate a full weekend itinerary.
                </p>
              </div>
            ) : (
              <div className="panel p-4">
                <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                  <Sun className="w-4 h-4" />
                  Weekend Planning — {cap(s.city)}
                </h2>
                <div className="scroll-content pr-1">
                  <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{s.itinerary}</ReactMarkdown></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ TAB 5: BROCHURE ════════════════ */}
      {tab === 5 && (
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-5">
          {/* Sidebar */}
          <div className={`panel p-4 ${sidebarOpen ? "" : "hidden"} md:block`}>
            <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
              <FileText className="w-4 h-4" />
              Brochure Cover
            </h2>

            {!s.itinerary ? (
              <p className="text-xs text-gray-400">Generate a weekend itinerary first in the Planning tab.</p>
            ) : (
              <div className="space-y-3">
                <button
                  onClick={handleFindCoverImages}
                  disabled={s.coverImagesLoading}
                  className="btn btn-primary btn-sm w-full"
                >
                  {s.coverImagesLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Searching…
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <Image className="w-4 h-4" />
                      Find Cover Images
                    </span>
                  )}
                </button>

                {/* Thumbnail gallery */}
                {s.coverImages.length > 0 && (
                  <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
                    <p className="text-xs font-medium text-gray-600 mb-1">
                      {s.coverImages.length} images found — click to select
                    </p>
                    {s.coverImages.map((img, i) => (
                      <div
                        key={i}
                        onClick={() => update("selectedCoverImage", img)}
                        className={`flex items-start gap-2 p-1.5 rounded-lg border cursor-pointer transition-all ${
                          s.selectedCoverImage?.url === img.url
                            ? "border-brand-blue bg-blue-50/60 ring-1 ring-brand-blue"
                            : "border-base-300 hover:border-gray-400"
                        }`}
                      >
                        <div className="w-16 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-100">
                          <img
                            src={img.thumb}
                            alt={img.title}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = "none";
                              (e.target as HTMLImageElement).parentElement!.classList.add("flex", "items-center", "justify-center", "text-xs", "text-gray-400");
                              (e.target as HTMLImageElement).parentElement!.innerText = "N/A";
                            }}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-700 truncate">{img.title}</div>
                          <div className="text-[11px] text-gray-400 truncate">{img.source}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {!s.coverImagesLoading && s.coverImages.length === 0 && (
                  <p className="text-xs text-gray-400">Click "Find Cover Images" to search for city photos.</p>
                )}

                {s.selectedCoverImage && (
                  <>
                    <hr className="border-base-300 my-1" />
                    <button
                      onClick={handleGeneratePDF}
                      disabled={s.pdfLoading}
                      className="btn btn-primary btn-sm w-full"
                    >
                      {s.pdfLoading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Generating PDF…
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <FileText className="w-4 h-4" />
                          Generate PDF
                        </span>
                      )}
                    </button>
                  </>
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
                  <path d="M2.25 15.75l5.25-4.75L12 13.5l4.5-4.25 5.25 4.75V6.75l-9.75 7.5-5.25-4.5-5.25 4.5v1.5z"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 6</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Create Your Brochure</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Generate a weekend itinerary first, then pick a cover image and export as a polished PDF brochure.
                </p>
              </div>
            ) : s.selectedCoverImage ? (
              <>
                {!s.pdfUrl && (
                  <div className="panel p-4 text-center">
                    <p className="text-sm text-gray-500">Cover image selected. Click <strong>Generate PDF</strong> in the sidebar.</p>
                  </div>
                )}
                {s.pdfUrl && (
                  <div className="panel p-4">
                    <h2 className="text-sm font-semibold text-brand-blue mb-3 flex items-center gap-1.5">
                      <FileText className="w-4 h-4" />
                      Brochure — {cap(s.city)}
                    </h2>
                    <div className="rounded-lg overflow-hidden border border-gray-200">
                      <iframe
                        src={`${apiBase}${s.pdfUrl}`}
                        title="PDF Preview"
                        className="w-full"
                        style={{ height: "600px", border: "none" }}
                      />
                    </div>
                    <a
                      href={`${apiBase}${s.pdfUrl}`}
                      className="btn btn-primary btn-sm mt-3 gap-1.5"
                      target="_blank"
                    >
                      <Download className="w-4 h-4" />
                      Download PDF
                    </a>
                  </div>
                )}
              </>
            ) : (
              <div className="panel p-8 text-center">
                <svg className="w-14 h-14 mx-auto mb-4 text-brand-blue/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M2.25 15.75l5.25-4.75L12 13.5l4.5-4.25 5.25 4.75V6.75l-9.75 7.5-5.25-4.5-5.25 4.5v1.5z"/>
                </svg>
                <div className="flex items-center justify-center gap-3 mb-3">
                  <div className="h-px w-8 bg-brand-gold/40" />
                  <span className="text-xs font-medium text-brand-gold uppercase tracking-widest">Step 6</span>
                  <div className="h-px w-8 bg-brand-gold/40" />
                </div>
                <h3 className="text-lg font-semibold text-brand-blue mb-1">Select a Cover Image</h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto leading-relaxed">
                  Use the sidebar to search for representative city photos. Click one to select it, then generate your PDF brochure.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Footer ── */}
      <footer className="mt-10 text-center text-xs text-gray-400 pb-6">
        &copy; DBG Travel 2026
      </footer>
    </div>
  );
}