# Jätskiauto Helsinki Metro — Route Map

Interactive map of ice cream truck (jätskiauto) routes across the Helsinki metropolitan area.
152 routes · 6,332 stops · GPS coordinates · full season timetables · live truck animation.

**Live map:** deployed on Vercel (connect the repo at vercel.com → auto-deploys on every push)

## Files

| File | Purpose |
|------|---------|
| `map.html` | Interactive Leaflet map |
| `metro_ice_cream_routes.json` | Routes + stops with GPS + schedules for the full season |
| `meta.json` | Last fetch date, route/stop counts |
| `fetch_routes.py` | Fetches all data from the API |
| `enrich_routing.py` | (Optional) Pre-computes road-following paths via OSRM |
| `view_routes.py` | CLI inspection of the JSON output |

## Refreshing data

```bash
# Fetch all metro routes (~5–10 min)
python fetch_routes.py

# Inspect the output
python view_routes.py
```

Requirements: `pip install requests`

## Season refresh

| When | Why |
|------|-----|
| **Start of season** (first operating day) | The API returns today's visits as `"Tänään klo: HH:MM"` on day 1 only. Run the fetcher on that day to capture those. |
| **Any other day** | Dated entries are stable all season — no re-fetch needed. |
| **New season (2027+)** | Re-run on the first operating day. |

## Data source

**api.paikannuspalvelu.fi** — the same API that powers the live customer tracking map.

```
GET /v1/public/route/                    → list of all routes
GET /v1/public/route/search/?routes=...  → stops with GPS + schedules
```

## Output schema

```json
[
  {
    "route_id":   "11_123_22",
    "route_name": "REITTI 11_123_22 TIISTAI",
    "weekday":    "tuesday",
    "stops": [
      {
        "name":      "Sinitiaisenpolku/Sinitiaisentie",
        "zip":       "02660",
        "lat":       60.23305,
        "lon":       24.81244,
        "schedules": [
          { "date": "2026-04-10", "time": "15:30", "weekday": "friday" }
        ],
        "path_to_next": [[60.233, 24.812], ...]
      }
    ]
  }
]
```

## Coverage

- **Helsinki** (00xxx), **Vantaa** (01xxx), **Espoo/Kauniainen** (02xxx)
- Monday–Saturday (no Sunday routes)
