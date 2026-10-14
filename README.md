# YATRAFLOW / STUDIO

**Local Python crowd digital twin and live browser dashboard.**

## Start (macOS / Windows / Linux)

1. Unzip the project.
2. Open a terminal in the `YatraFlow_Studio` folder.
3. Run `python3 start.py` (Windows: `py start.py`).
4. The dashboard automatically opens at **http://127.0.0.1:8000**.
5. Press `Ctrl+C` in the terminal to stop the server.

**No pip install required.** Python 3.10+ recommended. If port 8000 is occupied: `python3 start.py --port 8080`. To avoid auto-opening: `python3 start.py --no-browser`.

## Features

- Live server-authoritative agent simulation, canvas-rendered stylized 2.5D map, animated red tourist particles, zone occupancy, alerts, acknowledge/resolve workflow, forecasting, trace chart, tourism research view, tourist guidance and scenario presets.
- Developer Mode: target crowd, time speed, walking speed, dwell time, site share, arrival multiplier, year, month, hour, risk thresholds, festival/rain, gate restrictions, diversion, pause/reset and JSON export.
- Multiple browser tabs share the same live state.
- Source data bundled: 2021, 2025, provisional Jan–Aug 2026 Bodh Gaya tourism figures; 44,184 hourly weather rows from supplied Open-Meteo spreadsheet.
- Fully local application logic. Web fonts and the tourist-page photo load externally if the browser has internet; fallback fonts and all simulation features work offline.

## Accuracy / honesty

- **Exact within the simulator:** current agent count, admissions/exits counters, nearest-zone occupancy counts, and deterministic routing geometry.
- **Estimated:** walking speeds, dwell times, visitor site share, attraction preferences, gate allocation, capacities, route congestion and event multipliers.
- **Not real-time physical monitoring:** no live CCTV or gate sensors are connected. The map is schematic, not a surveyed temple plan.
- **Forecast:** an explicitly labeled damped trend heuristic, not a trained ML model or validated safety forecast.
- **Tourism:** city-wide monthly visits, not direct counts inside the temple. Unreported 2026 months are null.
- **Weather:** observed/reanalysis historical weather rows, aggregated for the selected month and hour. Weather does not imply a measured causal effect on arrivals.
- **Important:** the target crowd slider sets baseline desired population; festival, rain, and arrival multiplier modify the effective target. The effective target is capped at 2,600 agents for performance. The; agents are added or depart through simulated routes, so the live population approaches rather than instantaneously equals the target.

## Data sources

1. User-provided Bihar Tourism annual/monthly visitor sheets for 2021, 2025 and provisional 2026 (through August).
2. User-provided Open-Meteo hourly export at 24.71° N, 84.9839° E, elevation 125m. Bundled in `data/weather_hourly.json`.
3. User-provided India Tourism Data Compendium 2024 and 2025 provide national context; they are not mixed into the zone-level counts.

## API

- `GET /api/health`, `GET /api/state`, `GET /api/tourism`, `GET /api/weather`, `GET /api/export`
- `POST /api/config` JSON object of config changes
- `POST /api/reset` `{}`
- `POST /api/alert` `{ "id": "Central Plaza", "action": "acknowledged" }`

## Project structure

- `start.py` — single-entry Python standard-library web server + simulation engine
- `static/index.html` — application shell and dashboards
- `static/style.css` — brutalist gray-scale interface
- `static/app.js` — live canvas 2.5D visualization and controls
- `data/weather_hourly.json` — actual hourly weather records from upload
- `tests/test_engine.py` — deterministic unit tests

**Security:** bound to localhost (`127.0.0.1`) by default. Developer endpoints have no authentication; do not expose this demo to the public internet.

## V2 — Glass / brutalist interface and 1 km² district map

- Larger readable typography, soft frosted glass surfaces, rounded buttons and panels, Lucide icons (loaded via CDN), animated tactile sliders and iOS-like switches.
- Command map is anchored to approximately 1 km × 1 km around Mahabodhi Temple (24.69593 N, 84.99139 E).
- Actual mapped landmark anchors: Mahabodhi Temple (OSM way 314531108), Archaeological Museum (OSM way 312572546), Muchalinda Sarovar (OSM way 274190414).
- OpenStreetMap raster basemap loads live via `tile.openstreetmap.org` and requires internet. Offline, a procedurally illustrated fallback map remains visible. Basemap copyright © OpenStreetMap contributors; see https://www.openstreetmap.org/copyright. Do not use the public tile server for bulk scraping or high-volume deployment.
- Walking links, modeled entries, zone capacities and simulation agent behavior are **not** field-surveyed; this is a georeferenced educational digital twin, not a navigation or public-safety system.
- Original visitor data, historical weather records, simulator API, developer controls and tests are preserved.
- Icon and font CDNs require internet; navigation and controls remain functional if unavailable.
