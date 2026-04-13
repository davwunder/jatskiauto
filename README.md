# Jätskiauto Helsinki Metro — Route Map

Interactive map of ice cream truck (jätskiauto) routes across the Helsinki metropolitan area,
with GPS stops, full season timetables, and live truck animation.

## Files

| File | Purpose |
|------|---------|
| `fetch_routes.py` | Fetches all data from the API → writes `metro_ice_cream_routes.json` |
| `metro_ice_cream_routes.json` | Output: routes + stops with GPS + schedules for the full season |
| `meta.json` | Generated: last fetch date, route/stop counts |
| `map.html` | Interactive Leaflet map — open via local server |
| `enrich_routing.py` | (Optional) Pre-computes road-following paths via OSRM |
| `view_routes.py` | Quick CLI inspection of the JSON output |

## Viewing the map

```bash
# Run from the project folder (use full Python path on Windows if needed)
& "C:\Users\wunidavu\AppData\Local\anaconda3\python.exe" -m http.server 8000
# then open http://localhost:8000/map.html
```

For static hosting (no server needed), generate `data.js` first — see GitHub Pages section below.

## Fetching / refreshing data

```bash
# Fetch all metro routes (~5–10 min, one HTTP request per route)
python fetch_routes.py

# Also generate data.js for static hosting
python fetch_routes.py --export-js

# Inspect the output
python view_routes.py                  # summary table of all routes
python view_routes.py 11_123_22        # drill into a specific route
```

Requirements: `pip install requests`

## Season refresh

The season typically runs **April–September**. Here's when to re-run `fetch_routes.py`:

| When | Why |
|------|-----|
| **Start of season** (first operating day) | The API returns today's visits as `"Tänään klo: HH:MM"` on the first day only. Running the fetcher on that day captures those dates. |
| **Any other day** | The dated schedule entries (e.g. `"Ti 14.04.2026 klo: 14:50"`) are stable all season — no re-fetch needed. |
| **New season (2027+)** | Re-run on the first operating day of the new season. |

If you miss the first day, the only consequence is that today's stops won't show the animated trucks — all future scheduled visits are still correct.

## GitHub Pages (static hosting)

No server required if you use `data.js`:

```bash
python fetch_routes.py --export-js
```

This writes `data.js` (`window.ROUTE_DATA = [...]`). The map automatically uses it when
no server is available. Then:

1. Create a GitHub repo and push the project folder
2. Go to Settings → Pages → Source: main branch / root
3. Open `https://<username>.github.io/<repo>/map.html`

## Data source

The live customer map at asiakasnakyma.jatskiauto.com is powered by
**api.paikannuspalvelu.fi**. Key endpoints:

```
GET /v1/public/route/                    → list of all routes
GET /v1/public/route/search/?routes=...  → full stop data with GPS + schedules
```

## Output schema

`metro_ice_cream_routes.json` is a list of route objects:

```json
[
  {
    "file":       "route_907.json",
    "route_id":   "11_123_22",
    "route_name": "REITTI 11_123_22 TIISTAI",
    "weekday":    "tuesday",
    "zips":       ["02200", "02210"],
    "stops": [
      {
        "name":      "Sinitiaisenpolku/Sinitiaisentie",
        "zip":       "02660",
        "lat":       60.23305,
        "lon":       24.81244,
        "sequence":  1,
        "phone":     "0408517385",
        "schedules": [
          { "date": "2026-04-10", "time": "15:30", "weekday": "friday" },
          { "date": "2026-04-24", "time": "15:30", "weekday": "friday" }
        ],
        "path_to_next": [[60.233, 24.812], ...]  // only if enrich_routing.py was run
      }
    ]
  }
]
```

## Coverage

- **Helsinki** (00xxx), **Vantaa** (01xxx), **Espoo/Kauniainen** (02xxx)
- Monday–Saturday (no Sunday routes)
- Routes excluded: `poista` (marked for deletion), `VANHA WESTEND` (legacy)
- All stops have GPS coordinates from the tracking API — no geocoding needed
