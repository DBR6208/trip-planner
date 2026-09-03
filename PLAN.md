# Trip Planner Modernization Plan

## Purpose

Improve the reliability, security, editorial control, and visual relevance of the
trip-planning application. The target experience is:

1. Generate a useful first draft of a travel brochure.
2. Let the user edit one coherent Markdown document with a controlled set of
   LaTeX-compatible layout commands.
3. Preview the resulting PDF inside the application, without opening a new tab
   or automatically creating a download.
4. Select a city-defining, licensed cover image (for example, the Eiffel Tower
   for Paris or the Kölner Dom for Cologne), rather than an incidental city
   image.
5. Return route and charging advice only when it is feasible according to road
   routing and battery constraints.

This plan is intentionally phased. Do not expose the application publicly before
Phases 1 and 2 are complete.

## Scope and principles

- Treat all browser input, LLM output, search output, map data, URLs, and image
  metadata as untrusted.
- Keep third-party API keys server-side.
- Prefer structured data between services. Render Markdown, HTML, and LaTeX in
  a small number of dedicated modules.
- Preserve user choice: AI produces a ranked draft or candidate set; it must not
  silently make irreversible editorial choices.
- Add automated tests together with each changed backend behavior.
- Do not use generic image search results as automatically embedded brochure
  assets without a relevance and license check.

## Phase 0 — Establish a safe baseline

### Work

1. Create a Python test environment and install backend dependencies.
2. Install frontend dependencies and make `npm run build` and `npm run lint`
   required local/CI checks.
3. Add a CI workflow that runs:
   - Python formatting/linting and unit tests.
   - `python -m compileall backend`.
   - Frontend type check, lint, and production build.
4. Add a `.env.example` containing only variable names and documentation, never
   real keys.
5. Add structured application logging with request IDs. Ensure exceptions are
   logged with stack traces server-side but are not returned verbatim to clients.

### Acceptance criteria

- A clean checkout can run the documented checks.
- CI fails on type errors, test failures, or invalid formatting.
- Client error responses contain a safe message and request ID, not provider
  errors, file paths, or credentials.

## Phase 1 — Secure the public API and PDF pipeline

### 1.1 Authentication, CORS, and resource protection

1. Replace the permissive CORS configuration in `backend/main.py` with an
   environment-configured allowlist such as `FRONTEND_ORIGINS`.
2. Remove `allow_credentials=True` unless cookie-based authentication is
   explicitly introduced. Wildcard origins and credentials must not be used
   together.
3. Require authentication before deploying beyond a trusted local network.
   Start with a simple server-side API token or session; move to user accounts
   only if multi-user sharing is required.
4. Add per-IP and per-user rate limits for LLM, search, route, image, and PDF
   endpoints. Apply body-size limits and maximum lengths/counts to requests.
5. Add timeouts, retry rules, concurrency limits, and cost telemetry around
   OpenRouter, Tavily, Google, ORS, Firecrawl, and PDF generation.
6. Cache stable results by normalized city/country, landmark, hotel ID, and
   route inputs. Cache failures only briefly.

### 1.2 Replace loose dictionaries with explicit schemas

1. Replace `dict` and `list[dict]` request models with Pydantic models for
   hotels, restaurants, stations, maps, and brochure sections.
2. Validate coordinate ranges, non-empty IDs, maximum string lengths, battery
   percentages (0–100), cuisine values, and maximum number of station stops.
3. Do not trust client-submitted station metadata. Prefer a station ID returned
   by the backend, then reload station coordinates and name from the backend
   dataset before planning.
4. Define a common `ApiError` response shape with a safe error code and request
   ID.

### 1.3 Make PDF generation safe

1. Replace free-form `PDFRequest` fields with either:
   - a server-owned brochure draft ID, or
   - a single validated editor document plus references to server-owned assets.
2. Remove client-supplied `restaurant_map_html`. Generate map images only from
   backend-owned structured location data.
3. Remove arbitrary `hotel_photo_url` and `cover_image` URL fetching from the
   PDF endpoint. The endpoint must accept an approved image asset ID only.
4. Store downloaded assets in a controlled application directory, with a
   generated ID, MIME-type verification, decoded-image validation, size limits,
   and a maximum pixel count.
5. Do not allow arbitrary local paths as cover image paths.
6. Disable arbitrary raw LaTeX for normal generated content. Use an explicit,
   allowlisted editor syntax for advanced layout blocks (Phase 3).
7. Compile PDFs in a restricted worker/container with no network access,
   no shell escape, a read-only template directory, and a dedicated temporary
   output directory. Set CPU, memory, execution-time, and output-size limits.
8. Persist only the final PDF and explicitly approved assets. Make generated
   Markdown/debug artifacts optional, access-controlled, and subject to cleanup.
9. Validate that the requested download filename is a generated file ID, rather
   than accepting an arbitrary path-like name.

### Acceptance criteria

- An unauthenticated internet client cannot consume paid APIs or create PDFs.
- No endpoint fetches arbitrary URLs, executes client HTML, or reads arbitrary
  local paths.
- Malicious Markdown/LaTeX, HTML, oversized images, invalid MIME types, and
  unexpected station payloads are rejected safely.
- A PDF timeout or compiler failure cannot take down API workers.

## Phase 2 — Correct route and charging logic

### Work

1. Define battery policy explicitly:
   - departure battery;
   - minimum emergency reserve;
   - target arrival reserve;
   - charging target and charging-time model;
   - whether route recommendations optimize stops, driving time, charging time,
     preferred networks, or a weighted combination.
2. Use actual ORS road distances/durations for every proposed leg. Do not use
   latitude/longitude line length multiplied by 111 as the battery distance.
3. Build a route corridor from the ORS geometry only to shortlist stations; then
   calculate actual road legs for candidate station transitions.
4. Only consider stations ahead of the current route position. Never use an
   absolute projected-distance comparison that permits a stop behind the car.
5. Replace the nearest-neighbour reordering in `_plan_leg` with a constrained
   route-order/graph search. A stop is valid only when:
   - the leg can be routed;
   - arrival battery stays at or above the emergency reserve;
   - the selected charger has enough subsequent reachability;
   - the final destination meets the target arrival reserve.
6. Return a structured `route_infeasible` result when no valid chain of stops
   exists; never return a partial route as a successful plan.
7. When calculating the return trip, begin from the actual outbound final
   battery after selected charging stops—not the battery from an imaginary
   direct outbound drive.
8. Use ORS duration in trip summaries instead of a fixed 80 km/h speed.
9. Support direct outbound and return trips. Remove the frontend requirement
   that forces at least one outbound charging stop.
10. Expose why a recommended stop was chosen: road distance, predicted arrival
    percentage, charge amount, next-leg reachability, brand, and detour.

### Tests

- Short route requiring no charge.
- One-stop, multi-stop, and no-feasible-stop routes.
- Candidate station behind the current route position.
- ORS leg failure.
- Selected stops in an incorrect order.
- Return battery calculated after an outbound charge.
- Boundary cases at reserve thresholds.

### Acceptance criteria

- Every displayed leg has a successful ORS route and a non-negative, policy-
  compliant battery prediction.
- The UI can render a direct trip without requiring a charger.
- Infeasible trips explain the reason and do not create misleading summaries.

### 2.1 Replace the stale charging-station dataset with TomTom EV routing

The existing `unique_locations.csv` is approximately two years old and must not
remain the primary source of charging-station recommendations. Integrate TomTom
Long Distance EV Routing as the primary route-and-charging provider. Its
freemium tier is suitable for initial personal/small-scale use; record the
current account limits and alert before approaching them. Keep the CSV only as
an explicitly labelled offline/degraded fallback during migration.

1. Add `TOMTOM_API_KEY` and a `CHARGING_PROVIDER=tomtom|offline` setting to
   `.env.example` and the configuration module.
2. Create a provider interface, for example `EVRouteProvider`, returning a
   normalized response independent of TomTom:
   - route geometry, road distance, and traffic-aware duration;
   - per-leg road distance/duration and battery state;
   - charging-stop ID, name, operator, coordinates, connector, power, charge
     target, charging duration, detour, and source timestamp;
   - infeasibility/fallback reasons and provider diagnostics safe for the UI.
3. Implement `TomTomEVRouteProvider` using Long Distance EV Routing with the
   vehicle's battery capacity, current charge, consumption model, compatible
   connectors, minimum charge at stops, minimum destination reserve, and
   charging-time assumptions.
4. Make these vehicle values configurable rather than hard-coded. The car's
   usable capacity, consumption curve, CCS/Type-2 compatibility, maximum DC
   charge rate, departure state of charge, and desired reserve should be visible
   and editable in a Vehicle Settings panel.
5. Normalize operator names and aliases, then rank preferred networks such as
   Circle K, IONITY, Fastned, Allego, Shell, EnBW Mobility, and E.ON Drive.
   Preference is a ranking/selection rule, not permission to recommend an
   unreachable or unsuitable station.
6. If enabled for the TomTom account, query live availability only for the
   displayed/recommended stations using the returned charging-park ID. Show
   available, occupied, reserved, unknown, and out-of-service connectors with
   an `updated_at` timestamp. Cache this status briefly (for example 1–5
   minutes), never as long-lived route data.
7. Treat live availability as a current snapshot, not a guarantee for a future
   trip. Provide a **Refresh live status** action and label unavailable data
   clearly. Do not claim a station is free when status is missing.
8. If the desired live-availability/EV Search product is not enabled under the
   selected TomTom plan, retain TomTom EV-routing stops without live status and
   use the normal station detail/link as a fallback. Do not depend on a
   private-preview or sales-only API for core route feasibility.
9. Retain Open Charge Map as an optional secondary/offline data source for
   static location, operator, connector, and comment/check-in information;
   do not present it as guaranteed real-time availability.
10. Add provider health, quota, request latency, cache-hit, and fallback metrics.

### 2.2 User-controlled charging-stop editor

The route generator proposes stops; the user always has the final decision.
Implement a visible **Charging Stops** editor in the Route step.

1. Show TomTom's suggested stops in their driving order, including operator,
   power/connector, predicted arrival battery, target charge, expected charge
   time, detour, and current availability where known.
2. Let the user:
   - accept all suggestions;
   - remove a suggested stop;
   - add a station from a route-corridor search/list;
   - replace a suggested stop with another candidate;
   - reorder manually selected stops where the intended travel direction permits;
   - choose a preferred operator/network and connector/power filters;
   - set the desired final reserve and charging target within safe vehicle limits.
3. Never trust free-form browser station names or coordinates. Every add/replace
   action submits a backend station ID returned by the selected provider; the
   backend reloads canonical station metadata before planning.
4. Each change triggers an explicit **Recalculate plan** operation. The backend
   recalculates every leg, optimal charging amount/time, route order, arrival
   reserve, detour, and availability references from the revised station list.
5. Do not silently reorder manually chosen stops. If their requested order is
   inefficient or infeasible, preserve the stated order in the preview and show
   a clear warning plus an optional **Optimize stops** alternative.
6. Reject an edited plan when any leg is unreachable, connector-incompatible,
   closed/unavailable under a required live-status constraint, or below the
   emergency reserve. Explain the failing leg and offer nearby alternatives.
7. Permit direct routes with zero charging stops. If a removed stop makes a plan
   infeasible, retain the user's edit in the draft but mark it invalid; never
   replace it invisibly.
8. Persist the selected/manual stops with the brochure draft and include the
   final route plan, data timestamp, provider attribution, and status caveat in
   the PDF.

### Tests for TomTom and stop editing

- Mock TomTom automatic charging-stop responses, including preferred and
  non-preferred operators.
- Validate conversion between battery percentage and kWh and all configured
  reserve thresholds.
- Verify a user can add, remove, replace, and reorder stops and that each edit
  requires canonical station IDs and recalculation.
- Verify an invalid manual order or unreachable leg returns a clear structured
  error without silently changing the selection.
- Verify live-status cache expiry, unavailable-status display, and refresh
  behavior.
- Verify the offline CSV/Open Charge Map fallback is visibly marked as not-live.

## Phase 3 — Add a proper Markdown and controlled LaTeX editor

### Product design

Add a new **Edit Brochure** step between itinerary generation and PDF export.
It owns one editable document that combines the city guide, hotel, restaurants,
journeys, and itinerary. Generated content becomes the first draft, not the
final uneditable output.

Use **DBG Travel** as the product name with a clear, consistent descriptor:
**Weekend Trip Planner** or **Travel Planning Studio**. Select one descriptor
for the primary UI/header and use the same wording in the brochure, metadata,
and deployment documentation. The descriptor must make the product's purpose
clear without changing the established DBG Travel identity.

Use a source-first CodeMirror 6 editor in React. It is a better fit than a
WYSIWYG Markdown editor because this application needs predictable Pandoc and
LaTeX source editing.

The layout should be a resizable split view:

```text
Markdown source editor | HTML/Markdown preview | PDF preview
```

On smaller screens, show these as tabs.

### Editor capabilities

1. Syntax highlighting for Markdown, YAML front matter, and supported LaTeX
   blocks.
2. Line numbers, undo/redo, search/replace, keyboard shortcuts, and autosave
   with an explicit “saved” indicator.
3. Toolbar/snippets for headings, lists, links, tables, images, page breaks,
   figure blocks, and captions.
4. A document outline generated from headings.
5. Inline diagnostics before compilation: invalid heading nesting, broken image
   asset IDs, unclosed fences, unsupported commands, and invalid figure widths.
6. A “Reset section to generated draft” action rather than a destructive reset
   of the whole brochure.

### Supported advanced syntax

Prefer explicit Pandoc raw-Latex blocks, not bare LaTeX mixed unpredictably into
normal prose. Examples:

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

Also provide a safer high-level figure syntax that the backend converts to
LaTeX:

```markdown
![Hotel exterior](asset:hotel-photo){ width=70% }
```

### LaTeX safety policy

1. Normal generated text must not contain raw LaTeX.
2. Advanced editor blocks may contain only an allowlist of commands and
   environments needed for layout, initially:
   - `\newpage`, `\pagebreak`, `\clearpage`;
   - `figure`, `center`;
   - `\includegraphics`, `\caption`, `\centering`;
   - safe spacing commands if needed.
3. Reject `\input`, `\include`, `\usepackage`, `\write`, `\read`, `\openin`,
   `\openout`, `\immediate`, and all shell-escape-related commands.
4. Resolve `asset:<id>` only to approved server-side assets. Never pass a
   browser URL or local path directly to `\includegraphics`.
5. Validate width/height expressions against a small grammar, e.g. percentages
   or `0.1`–`1.0\textwidth`.

### Acceptance criteria

- A user can edit all brochure text and insert a page break or a 70%-width
  figure without manually changing the LaTeX template.
- Unsupported commands are shown as editor errors and compilation is blocked.
- The PDF uses exactly the saved editor document and approved asset IDs.

## Phase 4 — Inline PDF preview and deliberate downloads

### Work

1. Change PDF creation to an asynchronous preview job with states: queued,
   compiling, ready, failed, expired.
2. Provide separate backend routes:
   - `POST /api/brochures/{id}/preview` to create/update a preview;
   - `GET /api/brochures/{id}/preview.pdf` with `Content-Disposition: inline`;
   - `GET /api/brochures/{id}/download.pdf` with attachment disposition.
3. Place the preview route in an iframe in the PDF preview pane. Do not use
   `target="_blank"` for preview behavior.
4. Keep a distinct **Download PDF** button for the final, intentional download.
5. Debounce automatic preview generation, or require a **Compile preview**
   button, so each keystroke does not start XeLaTeX.
6. Revoke client-side blob URLs if blobs are used for preview transport.
7. Expire preview artifacts and assets after a configurable period.

### Acceptance criteria

- Editing and previewing never opens a new browser tab or forces a download.
- Downloading happens only after the user clicks Download PDF.
- Compilation errors appear inside the editor with useful, sanitized context.

## Phase 5 — Landmark-first city image selection

### Target behavior

For a city such as Paris, return photos labelled **Eiffel Tower**; for Cologne,
**Cologne Cathedral / Kölner Dom**; for Aachen, **Aachen Cathedral** and the
historic centre. Do not automatically return generic skyline, portrait, logo,
map, or unrelated building images.

### Data model

Introduce the following structured records:

```text
LandmarkCandidate:
  id, city, country, name, aliases, place_id, category, source_url, confidence

ImageCandidate:
  id, landmark_id, asset_url, thumbnail_url, provider, source_page_url,
  title, author, license, attribution, width, height, score, score_reasons
```

Store the selected image as an approved `ImageCandidate`/asset ID, not as a
free-form URL.

### Retrieval pipeline

1. **Normalize and disambiguate the destination.** Require city and country;
   geocode it and retain the canonical locality and country code.
2. **Discover 3–5 canonical landmarks.** Use Tavily, which is already present
   in the project, for focused discovery queries such as:
   - `Aachen Germany most iconic landmark official tourism`;
   - `Aachen Cathedral official tourism`;
   - `Aachen historic market square`.
   Restrict searches to reputable tourism, municipal, heritage, and reference
   domains where appropriate.
3. **Retrieve landmark-specific images.** Use Google Places Text Search/Place
   Photos as the primary practical source when a landmark has a place record.
   Query the landmark name, not only the city name.
4. **Retrieve official promotional images.** When a verified official tourism
   or city page is available, optionally use Firecrawl's single-page scrape to
   extract its hero images, Open Graph image, titles, and alt text. Do not use
   autonomous crawling/agents for every city.
5. **Use Wikimedia Commons/Wikidata as a licensing-friendly fallback.** Search
   the specific landmark/category, retain author/license/attribution metadata,
   and prefer high-resolution landscape images.
6. **Use Unsplash only as a generic aesthetic fallback.** It is suitable when
   no landmark photo is available, but must preserve the provider's required
   hotlinking and attribution rules.
7. **Do not make Serper a primary source.** It can expand Google Image-style
   candidate discovery, but results have uncertain licensing and should never
   be embedded automatically. Use it only as an optional, clearly labelled
   manual-selection fallback.

### Relevance ranking

1. Apply deterministic filters before any AI scoring:
   - minimum dimensions and landscape-preferred aspect ratio;
   - image MIME type and decoded-image validation;
   - reject URLs/titles suggesting maps, logos, icons, flags, portraits,
     screenshots, collages, or unrelated locations;
   - require city/landmark evidence in provider metadata, source page, or
     matched place ID.
2. Use a vision-capable model only to score the filtered thumbnails. Ask it to
   score landmark recognisability, city relevance, tourism-brochure composition,
   visual quality, and disallowed content.
3. Preserve score reasons, source, attribution, and landmark label for the UI.
4. Return a shortlist of 6–10 candidates grouped or labelled by landmark.
5. Preselect the highest-scoring candidate, but require/permit explicit user
   selection before final PDF generation.
6. Cache results by canonical city/country and refresh only when requested.

### Security and compliance

1. Never fetch a URL supplied directly by the browser. Fetch only provider URLs
   returned by approved discovery services and revalidate redirects, IP ranges,
   MIME type, byte size, and dimensions.
2. Maintain provider-specific attribution/licensing fields in the UI and PDF.
3. Validate allowed domains for official-tourism scraping; prevent private-IP,
   loopback, link-local, and metadata-service requests.
4. Add a manual “image is irrelevant” feedback action and record it for tuning.

### Acceptance criteria

- At least one of the top three candidates for Paris, Cologne, and Aachen is a
  recognizable canonical landmark.
- Every candidate shows its landmark label, source, and attribution/license
  status before selection.
- A user can reject all candidates and choose no cover image.
- No arbitrary external URL is fetched from a client request.

## Phase 6 — Improve editorial output and performance

### Work

1. Change LLM calls that produce facts into structured outputs with schemas:
   city guide sections, hotel summary, restaurant summary, itinerary blocks,
   landmarks, and image-evaluation scores.
2. Use a single batch call for restaurant descriptions, or remove generated
   one-line descriptions from the search stage. Do not issue one serial LLM call
   per restaurant result.
3. Keep LLM prompts separate from source data and clearly delimit search
   excerpts to reduce prompt-injection risk.
4. Add output validation and fallback templates for malformed or empty model
   results.
5. Correct `generate_maps_url` so query parameters use `&`, not encoded `%26`.
6. Centralize Markdown rendering and formatting. Services should return data;
   the brochure-draft renderer should be the sole formatter for headings, tables,
   lists, links, and separators.
7. Use a Markdown lint/parse step before editor preview and PDF compilation.

### Acceptance criteria

- A typical restaurant search has bounded LLM calls independent of the number
  of returned restaurants.
- All generated Google Maps links resolve correctly.
- The initial brochure draft has consistent heading hierarchy, lists, and
  tables, and is valid before the user begins editing.

## Phase 7 — Delivery sequence and rollout

1. Deliver Phase 0 first and record baseline test/build results.
2. Deliver Phase 1 before any shared or internet-facing deployment.
3. Implement Phase 2 with fixture-based tests and manually verify several
   Belgian/German/French routes.
4. Implement the editor and inline preview (Phases 3–4) behind a feature flag.
5. Implement landmark-first retrieval (Phase 5) behind a feature flag; evaluate
   Paris, Cologne, Aachen, Bruges, and a less famous city before enabling it by
   default.
6. Complete Phase 6 and remove obsolete formatting/image code only after the
   new workflows have production-equivalent test coverage.

## Phase 8 — Docker packaging and deployment

### Prerequisites

Complete the PDF input hardening in Phase 1 before treating Docker as a security
boundary. Containers reduce the blast radius of a failure; they do not make
arbitrary HTML, URLs, LaTeX, or unauthenticated API calls safe.

### Target architecture

```text
Browser
  |
  v
frontend (Nginx, built React application, public port only)
  |  /api and /static reverse proxy
  v
api (FastAPI, internal Compose network)
  |  brochure job request
  v
pdf-worker (Pandoc/XeLaTeX and controlled map/image rendering)
  |
  v
named volume: approved assets and generated brochures
```

Redis or another small job queue may be added between the API and PDF worker
when asynchronous preview/final PDF jobs are implemented. It is not required for
the first local development Compose setup, but should be used before supporting
multiple concurrent users.

### Files to add

```text
compose.yaml                     # local/default Compose definition
compose.production.yaml          # production overrides only
.dockerignore                    # excludes secrets, caches, builds, outputs
.env.example                     # variable names and safe example values
frontend/Dockerfile              # Node build stage + Nginx runtime stage
frontend/nginx.conf              # static assets + reverse proxy configuration
backend/Dockerfile               # API runtime image
backend/worker.Dockerfile        # optional dedicated PDF worker image
backend/entrypoint.sh            # startup checks and non-root launch
docker/seccomp-playwright.json  # browser sandbox profile, if Playwright remains
```

### Frontend container

1. Build the Vite application in a pinned Node image in the first stage.
2. Serve only the resulting static files from a small pinned Nginx runtime image.
3. Change frontend API configuration to use same-origin relative paths (`/api`)
   in production. Do not bake a localhost backend URL into the frontend build.
4. Configure Nginx to:
   - serve React assets with appropriate cache headers;
   - route SPA navigation to `index.html`;
   - proxy `/api/` and required `/static/` paths to the internal API service;
   - apply conservative response/request-size and timeout limits.
5. Publish only the frontend port, for example `8080:80`; the API and worker
   must not publish host ports by default.

### API and worker containers

1. Use a pinned Debian/Ubuntu-based Python image, not Alpine, because the
   application requires Pandoc, XeLaTeX packages, native geospatial libraries,
   image processing libraries, and potentially Playwright/Chromium.
2. Build dependencies should be installed before application code so Docker can
   reuse dependency layers.
3. Install only required TeX packages and remove package-manager caches in the
   same image layer to control image size.
4. Create and run as a dedicated non-root application user.
5. Use a read-only root filesystem where practical. Provide write access only to
   `/tmp` and the named volume for approved assets/generated brochures.
6. Set explicit CPU, memory, process, and execution-time constraints. Keep API
   worker counts low enough to respect LLM/search/provider quotas.
7. If map screenshots still require Playwright, pin the browser version to the
   package version. Run it as a non-root user with a suitable seccomp profile;
   do not use it to visit arbitrary URLs or HTML.
8. Move PDF compilation to `pdf-worker` after the job API from Phase 4 exists.
   The worker must have no outbound network access during compilation and only
   read approved document data and assets.
9. Add health checks for API readiness and worker/queue readiness. Use a restart
   policy appropriate for deployment.

### Data, persistence, and lifecycle

1. Create a named volume for final PDFs and approved downloaded images.
2. Do not mount the whole repository into production containers.
3. Do not persist raw third-party responses, temporary screenshots, debug
   Markdown, or compiler logs unless they are access-controlled and have an
   explicit retention policy.
4. Ensure generated brochures have an owner/job ID. The download and preview
   routes must authorize access to that owner/job.
5. Add a scheduled cleanup job for expired previews, intermediate files, and
   unused image assets.
6. Make backups of final brochures only if the product requires retention;
   otherwise expire them automatically.

### Configuration and secrets

1. Keep `.env`, secrets, output directories, frontend build artifacts,
   `node_modules`, Python virtual environments, and test caches out of Docker
   build contexts via `.dockerignore`.
2. Commit `.env.example` only. It must document `OPENROUTER_API_KEY`,
   `GOOGLE_MAPS_API_KEY`, `ORS_API_KEY`, `TAVILY_API_KEY`, optional Firecrawl
   configuration, allowed frontend origins, authentication configuration, and
   output retention settings—without values.
3. For local Compose development, pass a local ignored `.env` using
   `docker compose --env-file .env up --build`.
4. Update configuration loading to support `*_FILE` variables so a container can
   read Docker-secret files as well as ordinary environment variables.
5. In production, use Docker secrets or the deployment platform's secret store;
   grant each secret only to the container that needs it. The frontend receives
   no provider keys.
6. Provide separate development and production Compose configuration. Production
   must enable authentication, narrow CORS/origin configuration, health checks,
   restart policies, restrictive resource settings, and no source-code bind
   mounts.

### Compose workflow

1. `docker compose build` builds pinned frontend/API/worker images.
2. `docker compose up` starts the frontend, API, and any configured queue/worker
   dependencies.
3. `docker compose config` is run in CI to validate variable interpolation and
   the final Compose model.
4. Production deployment uses the base and override files, for example:

   ```powershell
   docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d --build
   ```

5. Document Windows Docker Desktop prerequisites and volume locations, since the
   project is developed on Windows but should run in Linux containers.

### Private remote access (Ubuntu GEEKOM)

The initial deployment is for the owner and a small group of trusted people,
not a public internet service. Use **Tailscale Serve** as the default remote
access mechanism rather than router port forwarding, a public IP address, or a
public tunnel.

1. Install Tailscale on the Ubuntu GEEKOM and on every approved user device.
   Invite only trusted people to the tailnet and use tailnet access controls to
   limit which users/devices can reach the GEEKOM.
2. Keep Docker's only published application port bound to loopback on the host,
   for example `127.0.0.1:8080:80`. Do not publish the FastAPI or PDF-worker
   ports.
3. Configure `tailscale serve` to proxy the GEEKOM's local frontend port over
   Tailscale HTTPS. Users access the stable `https://<machine>.<tailnet>.ts.net`
   URL while the React frontend continues to call its same-origin `/api` paths.
4. Run Tailscale as a system service and verify both Compose and Tailscale
   recover after reboot or power loss. Document the status, disable, and
   revocation procedures.
5. Keep application authentication and authorization from Phase 1 enabled:
   Tailscale restricts network reachability, but does not replace per-user
   access controls, audit logging, download authorization, or rate limits.
6. Do not use Tailscale Funnel for this private deployment. Funnel deliberately
   makes a service accessible to the public internet and requires the separate
   public-deployment security review.

### Tests and acceptance criteria

1. Add CI jobs that build all images, run API unit tests in the API image, run
   the frontend production build, and validate `docker compose config`.
2. Add a smoke test that starts Compose, waits for `/api/health` through the
   frontend proxy, and verifies the SPA is served.
3. Add an authenticated PDF-preview smoke test using a fixture brochure and a
   fixture image; it must not require external provider APIs.
4. Verify that only the frontend port is reachable from the host and that the
   API/worker are reachable only on the Compose network.
5. Verify no secret appears in image history, container logs, browser source,
   generated PDF, or source-control status.
6. Verify brochure files survive a container restart through the named volume,
   while temporary preview assets expire according to policy.
7. Verify the PDF worker cannot reach the public network during compilation and
   cannot write outside its temporary directory/output volume.
8. From an approved Tailscale device, verify the app is reachable over its
   Tailscale HTTPS URL; from a device outside the tailnet, verify it is not.

### Acceptance criteria

- A new developer can launch the complete local application with one documented
  Compose command and a local `.env` file.
- The browser accesses the app and API through a single frontend origin.
- Production containers run non-root with minimal writable storage, no exposed
  backend/worker ports, and managed secrets.
- Trusted users can access the GEEKOM-hosted app only through Tailscale Serve;
  the app has no router-forwarded or public application port.
- PDF generation works in Docker with the supported LaTeX, image, and map
  features, and fails safely when a dependency is unavailable.
- The image build is repeatable from pinned base images and dependency locks.

## Phase 9 — Optional local-model support

### Goal

Allow the application to use local Qwen models on the Ubuntu GEEKOM IT15 as a
private alternative for editorial and image-classification tasks. Local models
complement external search, mapping, and image providers; they do not replace
current factual discovery or routing services.

### Recommended initial model profile

For an IT15 with 32 GB RAM, begin with quantized models through Ollama:

| Purpose | Initial model | Usage policy |
|---|---|---|
| Fast rewriting, Markdown help, short classifications | Qwen3 4B Instruct, 4-bit | Low-latency tasks |
| Brochure drafts, itinerary JSON, synthesis | Qwen3 8B Instruct, 4-bit | Default local text model |
| Complex editing/reasoning | Qwen3 14B Instruct, 4-bit | On demand only; may be slow |
| Landmark/photo relevance scoring | Qwen3-VL 4B Instruct, 4-bit | Batch thumbnail review only |

Do not make 30B/32B models the default target for this hardware. They require
substantially more memory bandwidth and storage and are unlikely to be
interactive without a discrete GPU. Use non-thinking/Instruct mode for ordinary
brochure work; reserve deeper reasoning for explicit, latency-tolerant actions.

### Local-model task boundaries

Use local models for brochure drafting/rephrasing, structured-output cleanup,
Markdown assistance, safe LaTeX-layout suggestions, summarization of already
retrieved facts, route explanations based on calculated data, and filtered-image
ranking. Continue to use authoritative external providers for current travel
facts, places, routes, charging data, licensing, image-source verification, and
asset downloading.

### Provider abstraction

1. Generalize `services/llm.py` with `LLM_PROVIDER`, `LLM_BASE_URL`,
   `LLM_API_KEY`, `LLM_MODEL`, timeout, and retry configuration.
2. Retain OpenRouter as the cloud provider and add Ollama using its
   OpenAI-compatible `/v1` endpoint.
3. Use task-level model configuration, e.g. `TEXT_FAST_MODEL=qwen3:4b`,
   `TEXT_DRAFT_MODEL=qwen3:8b`, and `VISION_RANKING_MODEL=<Qwen3-VL tag>`.
4. Offer explicit Cloud quality, Local/private, and Automatic fallback modes.
   Display the mode/model that produced the output.
5. Automatic fallback may use cloud only with explicit user opt-in; it must
   never silently send private editor content to an external provider.
6. Keep the structured-output schemas and validation identical for cloud and
   local results.

### Ollama and Compose integration

1. Add an optional Compose profile called `local-llm` with an internal `ollama`
   service and a persistent named volume for model weights.
2. Point the API at `http://ollama:11434/v1`; do not expose port 11434 to the
   LAN by default.
3. Document a one-time model-pull procedure and a model health check. Do not
   bake model weights into application images.
4. Set per-task context/output limits and begin with one local generation at a
   time, so inference cannot starve the API, PDF worker, or Ubuntu host.
5. Treat Intel iGPU/NPU acceleration as optional and measured; CPU operation
   must work correctly first.
6. Keep the model service isolated from PDF-worker output volumes, provider
   secrets, and arbitrary URL access.

### Vision-ranking flow

1. Run the deterministic MIME, size, landscape, licensing, and landmark-metadata
   filters from Phase 5 before model evaluation.
2. Send only a filtered thumbnail plus a narrow JSON-only scoring request to
   Qwen3-VL.
3. Score landmark recognisability, city relevance, cover composition, and image
   quality; reject maps, logos, icons, portraits, interiors, and text-heavy or
   unconnected images.
4. Show the user each candidate's landmark label, score reasons, source, and
   attribution. The model ranks candidates but never makes the final selection.

### Tests and acceptance criteria

1. Add provider-contract tests against a mocked OpenAI-compatible local endpoint
   and an Ollama smoke test behind the `local-llm` Compose profile.
2. Benchmark Qwen3 4B and 8B with realistic brochure prompts on the IT15;
   record latency, peak RAM, output quality, and concurrent-PDF behavior.
3. Evaluate visual ranking with labelled Paris, Cologne, and Aachen candidates
   before enabling it by default.
4. Verify local-model failure does not block cloud mode, and automatic mode
   follows the user's privacy/fallback setting.

### Acceptance criteria

- Users can deliberately choose local/private generation for supported tasks.
- Qwen3 8B can produce a normal brochure draft without exhausting memory or
  blocking PDF generation on the target machine.
- Local ranking improves landmark relevance while retaining user choice.
- Model weights, secrets, and private editor content are not exposed through the
  frontend or unintended Docker ports.

## Definition of done

The modernization is complete when:

- Security controls prevent arbitrary URL/HTML/LaTeX execution and unauthorized
  use of paid APIs.
- Route results are demonstrably feasible and clearly explain failures.
- The brochure is editable in-app with safe page-break and figure-width tools.
- The PDF previews in-app and downloads only on explicit request.
- Cover-image candidates are landmark-specific, relevant, attributable, and
  user-selectable.
- Automated tests cover the critical security, routing, document, and image
  selection flows.
- The complete application can be launched and safely operated through Docker
  Compose using the Phase 8 deployment controls.
- Local-model mode is available as an optional privacy-preserving provider and
  has passed the Phase 9 benchmarks and contract tests.
