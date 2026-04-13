"""
enrich_routing.py — Pre-compute road-following geometry for ice cream truck routes.

Queries the OSRM public routing API for each route's full stop sequence and writes
a compact separate geometry file. The main routes JSON is NOT modified.

Output: metro_routes_geometry.json
  { "11_123_22": [[60.233,24.812],[60.234,24.813],...], ... }
  Keyed by route_id, value is the full stitched path (all legs concatenated).
  Estimated size: ~2–4 MB uncompressed, ~500 KB gzipped.

Usage:
    python enrich_routing.py [--dry-run] [--delay 0.25]

Options:
    --dry-run      Parse and report without writing output
    --delay N      Seconds to sleep between API requests (default 0.25)
    --input FILE   Input JSON file (default metro_ice_cream_routes.json)
    --output FILE  Output geometry JSON file (default metro_routes_geometry.json)
    --force        Re-fetch even if geometry file already exists for a route

Notes:
    • Uses the OSRM public demo server (router.project-osrm.org).
      For production / high-volume use, run your own OSRM instance.
    • ~152 routes → ~152 HTTP requests → roughly 45 seconds at default delay.
    • Re-running is safe: already-present route_ids are skipped unless --force.
    • Requires internet access.
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.error
import tempfile
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OSRM_BASE   = "http://router.project-osrm.org/route/v1/driving"
OUTPUT_FILE = "metro_routes_geometry.json"


# ── Atomic write ──────────────────────────────────────────────────────────────

def atomic_write_json(path: str, data, **kwargs) -> None:
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **kwargs)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── OSRM query ────────────────────────────────────────────────────────────────

def osrm_full_path(stops: list[dict]) -> list[list[float]] | None:
    """
    Query OSRM for a route through all stops in order.
    Returns a single stitched list of [lat, lon] pairs (all legs concatenated).
    Returns None on failure.
    """
    if len(stops) < 2:
        return None

    coords = ";".join(f"{s['lon']},{s['lat']}" for s in stops)
    url = f"{OSRM_BASE}/{coords}?overview=full&geometries=geojson&steps=false"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jatskiauto-map/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None

    if data.get("code") != "Ok":
        return None

    # With overview=full, the complete geometry is at the route level (not per leg)
    coords_raw = data["routes"][0]["geometry"]["coordinates"]
    path = [[c[1], c[0]] for c in coords_raw]   # flip [lon,lat] → [lat,lon]

    return path if path else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pre-compute OSRM road geometry")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output")
    parser.add_argument("--force",   action="store_true", help="Re-fetch already-present routes")
    parser.add_argument("--delay",   type=float, default=0.25, help="Sleep between API calls (sec)")
    parser.add_argument("--input",   default="metro_ice_cream_routes.json")
    parser.add_argument("--output",  default=OUTPUT_FILE)
    args = parser.parse_args()

    print("🍦 Jätskiauto Route Geometry Pre-computation (OSRM)")
    print(f"   Input    : {args.input}")
    print(f"   Output   : {args.output}")
    print(f"   Delay    : {args.delay}s between requests")
    if args.dry_run:
        print("   Mode     : DRY RUN (no writes)")
    print()

    with open(args.input, encoding="utf-8") as f:
        routes = json.load(f)

    if not isinstance(routes, list):
        routes = list(routes.values())

    # Load existing geometry file if present (for incremental updates)
    geometry: dict[str, list] = {}
    if os.path.exists(args.output) and not args.force:
        try:
            with open(args.output, encoding="utf-8") as f:
                geometry = json.load(f)
            print(f"   Loaded {len(geometry)} existing route(s) from {args.output}")
        except (json.JSONDecodeError, OSError):
            print(f"   ⚠️  Could not read {args.output} — starting fresh")
    print()

    total    = len(routes)
    fetched  = 0
    skipped  = 0
    failed   = 0

    for i, route in enumerate(routes, 1):
        route_id = route.get("route_id") or route.get("route_name", f"route_{i}")
        stops    = route.get("stops", [])

        if len(stops) < 2:
            skipped += 1
            continue

        if route_id in geometry and not args.force:
            skipped += 1
            continue

        print(f"  [{i:3d}/{total}] {route_id:<40} ", end="", flush=True)

        path = osrm_full_path(stops)

        if path:
            geometry[route_id] = path
            fetched += 1
            print(f"✅ {len(path)} pts")
        else:
            failed += 1
            print("⚠️  OSRM failed → skipped")

        if i < total:
            time.sleep(args.delay)

    print()
    print(f"✅ Fetched  : {fetched} route(s)")
    print(f"⏭️  Skipped  : {skipped} (already present or <2 stops)")
    print(f"⚠️  Failed   : {failed}")
    print(f"📦 Total in geometry file: {len(geometry)} route(s)")

    if not args.dry_run:
        atomic_write_json(args.output, geometry, ensure_ascii=False, separators=(',', ':'))
        size_kb = os.path.getsize(args.output) / 1024
        print(f"💾 Saved to {args.output} ({size_kb:.0f} KB)")
    else:
        print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
