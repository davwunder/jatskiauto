"""
🍦 Jätskiauto Helsinki Metro Route Fetcher
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetches all Helsinki metro area ice cream truck stops with GPS coordinates
and full season schedules from the paikannuspalvelu.fi tracking API.

Covers: Helsinki (00xxx), Vantaa (01xxx), Espoo/Kauniainen (02xxx)

Output: metro_ice_cream_routes.json  +  meta.json  [+  data.js if --export-js]

Requirements:
    pip install requests

Flags:
    --export-js   Also write data.js (window.ROUTE_DATA = [...]) for
                  static/GitHub Pages hosting without a local server
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date as _date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests

# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE  = "https://api.paikannuspalvelu.fi"
DATA_KEY  = "eVCPeXjwNNYMfGZ6sGwzLcFB462FTfgJ5TqAX7nf"
AUTHOR    = "rest@paikannuspalvelu.fi"
PARAMS    = f"data_key={DATA_KEY}&author={AUTHOR}&format=geojson"

# Full Helsinki metro area zip prefixes
METRO_PREFIXES = ("00", "01", "021", "022", "023", "026", "027", "028", "029")

OUTPUT_FILE = "metro_ice_cream_routes.json"
META_FILE   = "meta.json"
JS_FILE     = "data.js"
USER_AGENT  = "jatskiauto-route-mapper/1.0"

# Finnish weekday abbreviations → English
WEEKDAY_FI = {
    "ma": "monday",    "maanantai": "monday",
    "ti": "tuesday",   "tiistai": "tuesday",
    "ke": "wednesday", "keskiviikko": "wednesday",
    "to": "thursday",  "torstai": "thursday",
    "pe": "friday",    "perjantai": "friday",
    "la": "saturday",  "lauantai": "saturday",
    "su": "sunday",    "sunnuntai": "sunday",
}

TANAAN_RE = re.compile(r"^tänään\s+klo:\s+(\d{2}:\d{2})$", re.IGNORECASE)


# ── Schedule parsing ──────────────────────────────────────────────────────────

def parse_schedule(raw: str) -> dict | None:
    """
    Parse a single schedule string into a structured dict.

    "Ti 14.04.2026 klo: 14:50"  → {"date": "2026-04-14", "time": "14:50", "weekday": "tuesday"}
    "Tänään klo: 15:15"         → today's date with that time (first visit of the season)
    """
    stripped = raw.strip()

    m_today = TANAAN_RE.match(stripped)
    if m_today:
        today   = _date.today().isoformat()
        time    = m_today.group(1)
        weekday = WEEKDAY_FI.get(_date.today().strftime("%A").lower())
        return {"date": today, "time": time}

    m = re.match(
        r"^(\w+)\s+(\d{1,2})\.(\d{2})\.(\d{4})\s+klo:\s+(\d{2}:\d{2})$",
        stripped,
    )
    if not m:
        return None

    day_abbr, day, month, year, time = m.groups()
    weekday = WEEKDAY_FI.get(day_abbr.lower())
    try:
        date = f"{year}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None

    return {"date": date, "time": time}


# ── Route name parsing ────────────────────────────────────────────────────────

def parse_route_name(name: str) -> tuple[str | None, str | None]:
    """
    "REITTI 11_123_22 TIISTAI" → ("11_123_22", "tuesday")
    "VANHA WESTEND"            → (None, None)
    """
    m = re.match(r"REITTI\s+([\w_]+)\s+(\w+)", name, re.IGNORECASE)
    if m:
        route_id = m.group(1)
        weekday  = WEEKDAY_FI.get(m.group(2).lower())
        return route_id, weekday
    return None, None


# Routes to exclude — marked for deletion or replaced
EXCLUDED_ROUTE_NAMES = {"poista", "vanha westend"}


# ── Atomic file write ─────────────────────────────────────────────────────────

def atomic_write_json(path: str, data, **kwargs) -> None:
    """Write JSON atomically: write to a temp file, then replace the target."""
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, **kwargs)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


# ── Main ──────────────────────────────────────────────────────────────────────

def main(export_js: bool = False) -> None:
    print("🍦 Jätskiauto Helsinki Metro Route Fetcher\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    # ── Step 1: fetch the routes list ─────────────────────────────────────────
    print("📋 Fetching route list…")
    resp = session.get(f"{API_BASE}/v1/public/route/?{PARAMS}", timeout=15)
    resp.raise_for_status()
    all_routes = resp.json()

    metro_routes = [
        r for r in all_routes
        if any(z.startswith(METRO_PREFIXES) for z in r.get("zips", []))
    ]
    print(f"  Found {len(metro_routes)} metro route(s).")

    # Build lookup: file → route metadata
    file_to_meta: dict[str, dict] = {}
    for r in metro_routes:
        route_id, weekday = parse_route_name(r["name"])
        file_to_meta[r["file"]] = {
            "route_id":   route_id,
            "route_name": r["name"],
            "weekday":    weekday,
            "zips":       r["zips"],
            "file":       r["file"],
        }

    # ── Step 2: fetch stops per route ─────────────────────────────────────────
    print("📡 Fetching stops per route…")
    routes_output = []

    for r in metro_routes:
        meta = file_to_meta[r["file"]]

        if meta["route_name"].lower().strip() in EXCLUDED_ROUTE_NAMES:
            print(f"  ⏭️  Skipping '{meta['route_name']}' (excluded)")
            continue

        resp = session.get(
            f"{API_BASE}/v1/public/route/search/?routes={r['file']}&{PARAMS}",
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  🛑 Failed to fetch {r['file']}: {resp.status_code}")
            continue

        features = resp.json().get("features", [])
        metro_stops = [
            f for f in features
            if str(f["properties"].get("zip", "")).startswith(METRO_PREFIXES)
        ]

        if not metro_stops:
            continue

        stops = []
        for feat in sorted(metro_stops, key=lambda f: f["properties"].get("sequence_on_route", 0)):
            props  = feat["properties"]
            coords = feat["geometry"]["coordinates"]

            schedules = [
                s for s in (parse_schedule(raw) for raw in props.get("schedules", []))
                if s is not None
            ]

            stops.append({
                "name":      props.get("name_on_route"),
                "zip":       str(props.get("zip")),
                "lat":       coords[1],
                "lon":       coords[0],
                "phone":     props.get("contact"),
                "schedules": schedules,
            })

        route_entry = {
            "file":       r["file"],
            "route_id":   meta["route_id"],
            "route_name": meta["route_name"],
            "weekday":    meta["weekday"],
            "zips":       [z for z in r["zips"] if z.startswith(METRO_PREFIXES)],
            "stops":      stops,
        }
        routes_output.append(route_entry)
        print(f"  🍦 {meta['route_name']:45}  {len(stops)} stop(s)")

    # ── Step 3: summary & save ────────────────────────────────────────────────
    total_stops    = sum(len(r["stops"]) for r in routes_output)
    total_no_sched = sum(1 for r in routes_output for s in r["stops"] if not s["schedules"])

    print(f"\n✅ Done!")
    print(f"📋 Routes        : {len(routes_output)}")
    print(f"📍 Total stops   : {total_stops}")
    print(f"🗓️  No schedules  : {total_no_sched}")

    # Atomic JSON write (compact — no indent)
    atomic_write_json(OUTPUT_FILE, routes_output, ensure_ascii=False, separators=(',', ':'))
    print(f"💾 Saved to {OUTPUT_FILE}")

    # meta.json
    meta_data = {
        "generated": _date.today().isoformat(),
        "routes":    len(routes_output),
        "stops":     total_stops,
        "area":      "Helsinki metro (00xxx, 01xxx, 02xxx)",
    }
    atomic_write_json(META_FILE, meta_data, indent=2)
    print(f"💾 Saved to {META_FILE}")

    # Optional data.js for static hosting
    if export_js:
        js_content = "// Auto-generated by fetch_routes.py — do not edit manually\n"
        js_content += "window.ROUTE_DATA = "
        js_content += json.dumps(routes_output, ensure_ascii=False)
        js_content += ";\n"
        tmp_js = JS_FILE + ".tmp"
        with open(tmp_js, "w", encoding="utf-8") as f:
            f.write(js_content)
        os.replace(tmp_js, JS_FILE)
        print(f"💾 Saved to {JS_FILE} (static hosting bundle)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-js", action="store_true",
                        help="Also write data.js for GitHub Pages / static hosting")
    args = parser.parse_args()
    main(export_js=args.export_js)
