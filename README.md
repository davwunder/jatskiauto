# Jätskiauto Helsinki Metro

Interactive map of ice cream truck routes across the Helsinki metro area — Helsinki, Vantaa, Espoo and Kauniainen. 152 routes · 6,332 stops · GPS coordinates · full season timetables · live truck positions.

**[→ Open the map](https://jatskiauto.live)**

> **Disclaimer:** This is a personal vibe coding exercise built for fun. I have no affiliation with Jätskiauto or any ice cream company, and I am not paid by anyone for this. Data comes from the public API at [paikannuspalvelu.fi](https://api.paikannuspalvelu.fi) — the same API that powers the live customer tracking map.

**Data last refreshed:** 2026-04-14

---

## Using the map

Just open the link above — no installation needed. The map is a static site deployed on Vercel.

**Features:**
- Browse routes by date (full 2026 season)
- Click any stop to see the schedule and share a direct link
- 📍 Find the nearest active stop to your current location
- Live truck positions (updates every 30 s when viewing today)
- Address search powered by OpenStreetMap / Nominatim
- Routes-today list — click any route to zoom the map to it
- EN / FI language toggle

---

## Refreshing the data

The committed JSON files cover the full 2026 season. You only need to re-run the scripts when a new season starts.

**Requirements:** `pip install requests`

### Step 1 — Fetch routes from the API (~5–10 min)

```bash
python scripts/fetch_routes.py
```

Writes `metro_ice_cream_routes.json` and `meta.json` to the project root.

### Step 1b — Pre-compute road geometry (optional, ~1 min)

```bash
python scripts/enrich_routing.py
```

Writes `metro_routes_geometry.json`. When this file is present, the map draws routes along actual roads instead of straight lines. Uses the public [OSRM](http://router.project-osrm.org) routing server.

### Step 2 — Commit and push → Vercel auto-deploys

```bash
git add metro_ice_cream_routes.json meta.json metro_routes_geometry.json
git commit -m "Refresh data $(date +%Y-%m-%d)"
git push
```

Also update the **Data last refreshed** date in this README.

### Season timing

| When | Action |
|------|--------|
| **First operating day of the season** | Run `fetch_routes.py` — the API returns that day's first visits as `"Tänään klo: HH:MM"` on day 1 only |
| **Any other day** | No re-fetch needed — dated entries are stable all season |
| **New season (2027+)** | Re-run on the first operating day |

---

## Project layout

```
map.html                         The map application (Leaflet.js, single HTML file)
index.html                       Root redirect → map.html
metro_ice_cream_routes.json      Route + stop data with GPS and schedules (~2.9 MB)
metro_routes_geometry.json       Pre-computed road paths for each route (optional)
meta.json                        Last-fetch date, route count, stop count
scripts/
  fetch_routes.py                Step 1: fetch all metro routes from the API
  enrich_routing.py              Step 1b: pre-compute OSRM road geometry
  view_routes.py                 Helper: CLI inspection of the JSON output
```

The map (`map.html`) only needs the JSON files — no Python, no server, no build step. The scripts are only used to regenerate data.

---

## Data schema

```json
[
  {
    "route_id":   "11_123_22",
    "route_name": "REITTI 11_123_22 TIISTAI",
    "weekday":    "tuesday",
    "zips":       ["02100", "02110"],
    "stops": [
      {
        "name":      "Sinitiaisenpolku/Sinitiaisentie",
        "zip":       "02660",
        "lat":       60.23305,
        "lon":       24.81244,
        "schedules": [
          { "date": "2026-04-10", "time": "15:30" }
        ]
      }
    ]
  }
]
```

**Coverage:** Helsinki (00xxx) · Vantaa (01xxx) · Espoo / Kauniainen (02xxx) · Monday–Saturday
