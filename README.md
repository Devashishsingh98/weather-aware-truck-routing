# Weather-Aware Truck Routing

Public repo: [github.com/Devashishsingh98/weather-aware-truck-routing](https://github.com/Devashishsingh98/weather-aware-truck-routing)

A React and Django app that builds three driving options for a haul, samples wind, rain, and snow at the truck's estimated arrival, and recommends the corridor with the least weather exposure.

The example haul is Dallas, TX to Denver, CO with a 35,000 lb load. On a calm forecast the shortest drive wins. When a corridor enters Severe or No Travel weather, that mileage outranks a faster clear road.

## Run it locally

Backend (API on port 8741):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py test planner
python manage.py runserver 0.0.0.0:8741
```

Frontend (app on port 8742). The dev server proxies `/api` to the Django process, so leave `VITE_API_BASE_URL` empty.

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:8742. The form is filled with Dallas → Denver, tomorrow at 08:00 origin time, 35,000 lb, and a 25-mile sample interval. **Plan haul** runs the request. The first call is usually a few seconds; a cold forecast can take longer if the public routers are busy.

## Architecture

```
browser (Vite + React + Leaflet)
  POST /api/plan/       three routes, checkpoints, recommendation
  POST /api/heatmap/    49 hours of corridor risk, fetched once
  GET  /api/geocode/    place suggestions
        │
Django + DRF
  geocode.py     Photon, then Nominatim
  routing.py     OSRM driving, plus a perpendicular waypoint if needed
  sampling.py    checkpoint every 10 / 25 / 50 miles, ETA from segment time
  weather.py     batched Open-Meteo, cached 30 minutes
  risk.py        wind, rain, snow, and load rules
  scoring.py     mile totals and the recommendation order
```

The browser does not rescore weather. It draws what the API returns. The heatmap slider only swaps the hour index in a grid that is already in memory. Slider updates are debounced by 40ms and the canvas repaints on the next animation frame.

## APIs

All of these are free and need no key.

| Job | Service | Notes |
| --- | --- | --- |
| Geocoding | [Photon](https://photon.komoot.io) | Nominatim is the fallback |
| Routing | [OSRM public demo](https://router.project-osrm.org) | `driving` profile, `alternatives=true`, full geometry, duration and distance annotations |
| Weather | [Open-Meteo](https://api.open-meteo.com) | `wind_speed_10m` in mph, `rain` and `snowfall` in inches per hour |
| Map tiles | OpenStreetMap | CARTO's raster tiles now require an API key, so the map uses OSM |

OSRM often returns only one or two alternatives. Dallas to Denver returns two. The third option is another OSRM drive through a waypoint set perpendicular to the primary line, 25 to 110 miles off it. A candidate is kept only when sampled points sit at least 8 miles, on average, off the routes already chosen. The response includes `route_note` when this fallback is used.

Segment durations on the public server do not always sum to the published route duration (turn costs are missing from the annotation). Each leg's segment times are scaled so they sum to that leg's duration. The shape of slow and fast stretches is kept. Checkpoint ETA is departure plus that cumulative driving time.

## Risk rules

Bands are contiguous. A printed range such as "25–34" is the integer miles per hour in that band, so the next printed threshold is the exclusive upper bound.

| | Low | Moderate | High | Severe | No Travel |
| --- | --- | --- | --- | --- | --- |
| Wind (mph) | <25 | 25 up to 35 | 35 up to 45 | 45 up to 55 | ≥55 |
| Rain (in/hr) | <0.10 | 0.10 up to 0.25 | 0.25 up to 0.50 | 0.50 through 1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5 up to 1.0 | 1.0 up to 2.0 | 2.0 through 3.0 | >3.0 |

Rain and snow columns in the brief share their endpoints (0.25 is listed under both Moderate and High). The shared endpoint takes the worse band. No Travel for rain and snow is a strict greater-than, so 1.00 in/hr of rain and 3.0 in/hr of snow stay Severe. 34.9 mph is still Moderate. 35.0 mph is High. The same cut applies at 45 and 55.

Load rules only raise the wind result:

- ≥55 mph is No Travel for any load.
- 45 mph up to 55, and a load over 30,000 lb, is No Travel. Exactly 30,000 lb stays Severe.
- 35 mph up to 45, and a load over 40,000 lb, is raised to Severe. Exactly 40,000 lb stays High.

The checkpoint risk is the worst of wind-after-load, rain, and snow.

Miles between two checkpoints are charged to the worse of the two samples. The mileage-weighted average uses Low 0, Moderate 1, High 2, Severe 3, No Travel 4.

## Recommendation order

1. Fewest No Travel miles. Any No Travel mileage is disqualifying and worse than Severe, so it is its own sort key rather than being folded into Severe. A short blocked corridor loses to a longer clean one.
2. Fewest Severe miles.
3. Fewest High miles.
4. Lowest mileage-weighted average risk.
5. Shortest driving time.
6. Shortest distance, then route id, if the rest is tied.

If every option has No Travel miles, the app still ranks them and says the winner is the least exposed, not a clearance to roll.

`python manage.py test planner` covers the boundaries, the load cuts at 30,000 and 40,000 lb, segment miles, the full sort order, ETA sampling, forecast hour alignment, and OSRM annotation scaling.

## Assumptions

- Routes use OSRM's car `driving` profile. There is no truck network, so low bridges, hazmat, and weight restrictions are not applied.
- ETA ignores hours-of-service breaks, fuel, and weather slowdowns. The brief asks for departure plus cumulative driving duration.
- The departure clock time is local time at the origin. Open-Meteo supplies the IANA zone. Times on the map use that zone.
- Wind is the 10 m sustained speed, not the gust. Rain is liquid rain so snow is not counted twice. Snowfall is the inch depth rate Open-Meteo returns when `precipitation_unit=inch`.
- Forecast cells are rounded to 0.01° (about a kilometer) and cached in process for 30 minutes. A missing hour is scored as calm and flagged on the checkpoint.
- The forecast window is only as long as the haul needs, from one day back through the latest ETA (or departure plus 48 hours for the heatmap). Departures more than 12 hours in the past, or more than 6 days ahead, are rejected.
- The heatmap is a corridor, not the whole bounding box: points every 40 miles along each route, plus perpendicular offsets at 16 and 34 miles, capped at 72 locations.

## Deploy

No host credentials are available in this environment, so the app is not deployed. These steps are enough for the free tiers.

### API on Render

`render.yaml` is a Docker web service. From the Render dashboard, New → Blueprint, and connect [Devashishsingh98/weather-aware-truck-routing](https://github.com/Devashishsingh98/weather-aware-truck-routing). Set `CORS_ALLOWED_ORIGINS` to the frontend origin if it is not a `*.vercel.app` or `*.netlify.app` host. Those two suffixes are already allowed. The health check is `/api/health/`.

Or build the image yourself:

```bash
docker build -t weather-routing-api backend
docker run --rm -p 8741:8000 -e PORT=8000 -e DJANGO_ALLOWED_HOSTS=* weather-routing-api
```

`tzdata` is installed in the image so origin timezones resolve.

### Frontend on Vercel

Import [Devashishsingh98/weather-aware-truck-routing](https://github.com/Devashishsingh98/weather-aware-truck-routing) and set the project root to `frontend`. Framework preset Vite. Set `VITE_API_BASE_URL` to the Render origin with no trailing slash, for example `https://weather-truck-routing-api.onrender.com`. `frontend/vercel.json` rewrites client routes to `index.html`.

### Frontend on Netlify

Import [Devashishsingh98/weather-aware-truck-routing](https://github.com/Devashishsingh98/weather-aware-truck-routing). `netlify.toml` at the repo root builds `frontend`. Set the same `VITE_API_BASE_URL` in the Netlify UI. Vite inlines it at build time, so change it and rebuild when the API URL changes.

## Layout

```
backend/planner/services/   risk, scoring, routing, weather
backend/planner/tests/      unit tests, no network
frontend/src/               form, route list, Leaflet map, heatmap canvas
```
