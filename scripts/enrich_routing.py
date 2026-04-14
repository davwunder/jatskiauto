"""
enrich_routing.py — Pre-compute per-leg road geometry for ice cream truck routes.

Queries the OSRM public routing API for each consecutive stop pair and writes
one compact JSON file per route into a geometry/ directory.

Output: geometry/{route_id}.json
  Each file is an array of leg paths:
    [ [[lat,lon],...], [[lat,lon],...], ... ]
  One entry per consecutive stop pair (N-1 entries for N stops).
  A null entry means that leg's OSRM call failed — the map falls back to a
  straight line for that leg.

Coordinates are rounded to 4 decimal places (~11 m precision).

Usage:
    python enrich_routing.py [--dry-run] [--delay 0.25] [--force]

Options:
    --dry-run        Parse and report without writing output
    --delay N        Seconds to sleep between API requests (default 0.25)
    --input FILE     Input JSON file (default metro_ice_cream_routes.json)
    --output-dir DIR Output directory for per-route files (default geometry)
    --force          Re-fetch even if output file already exists for a route

Notes:
    • Uses the OSRM public demo server (router.project-osrm.org).
      For production / high-volume use, run your own OSRM instance.
    • ~152 routes × ~30 legs avg → ~4 500 HTTP requests → ~20 min at default delay.
    • Re-running is safe: already-present route files are skipped unless --force.
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

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"


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


# ── OSRM single leg ───────────────────────────────────────────────────────────

def osrm_leg(stop_a: dict, stop_b: dict) -> list[list[float]] | None:
    """
    Query OSRM for the road path from stop_a to stop_b.
    Returns a list of [lat, lon] pairs rounded to 4 decimal places.
    Returns None on failure.
    """
    coords = f"{stop_a['lon']},{stop_a['lat']};{stop_b['lon']},{stop_b['lat']}"
    url = f"{OSRM_BASE}/{coords}?overview=full&geometries=geojson&steps=false"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jatskiauto-map/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None

    if data.get("code") != "Ok":
        return None

    coords_raw = data["routes"][0]["geometry"]["coordinates"]
    return [[round(c[1], 4), round(c[0], 4)] for c in coords_raw]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pre-compute per-leg OSRM road geometry")
    parser.add_argument("--dry-run",    action="store_true", help="Do not write output")
    parser.add_argument("--force",         action="store_true", help="Re-fetch already-present routes")
    parser.add_argument("--retry-failed",  action="store_true", help="Re-fetch only routes with null legs")
    parser.add_argument("--delay",         type=float, default=0.25, help="Sleep between API calls (sec)")
    parser.add_argument("--input",         default="metro_ice_cream_routes.json")
    parser.add_argument("--output-dir",    default="geometry")
    args = parser.parse_args()

    print("🍦 Jätskiauto Per-leg Route Geometry Pre-computation (OSRM)")
    print(f"   Input      : {args.input}")
    print(f"   Output dir : {args.output_dir}")
    print(f"   Delay      : {args.delay}s between requests")
    if args.dry_run:
        print("   Mode       : DRY RUN (no writes)")
    if args.retry_failed:
        print("   Mode       : RETRY FAILED (re-fetch routes with null legs)")
    print()

    with open(args.input, encoding="utf-8") as f:
        routes = json.load(f)

    if not isinstance(routes, list):
        routes = list(routes.values())

    if not args.dry_run:
        os.makedirs(args.output_dir, exist_ok=True)

    total_routes = len(routes)
    fetched_routes = 0
    skipped_routes = 0
    failed_legs = 0
    total_legs = 0

    for i, route in enumerate(routes, 1):
        route_id = route.get("route_id") or route.get("route_name", f"route_{i}")
        stops = route.get("stops", [])

        if len(stops) < 2:
            skipped_routes += 1
            continue

        out_file = os.path.join(args.output_dir, f"{route_id}.json")

        if os.path.exists(out_file) and not args.force:
            if args.retry_failed:
                # Re-fetch only if file has null legs
                try:
                    with open(out_file, encoding="utf-8") as f:
                        existing = json.load(f)
                    if not any(leg is None for leg in existing):
                        skipped_routes += 1
                        continue
                    # Merge: only re-fetch the null legs
                    print(f"  [{i:3d}/{total_routes}] {route_id:<40} retrying {sum(1 for l in existing if l is None)} failed leg(s) … ", end="", flush=True)
                    route_failed = 0
                    for j, leg in enumerate(existing):
                        if leg is not None:
                            continue
                        new_leg = osrm_leg(stops[j], stops[j + 1])
                        if new_leg:
                            existing[j] = new_leg
                        else:
                            route_failed += 1
                        total_legs += 1
                        time.sleep(args.delay)
                    failed_legs += route_failed
                    atomic_write_json(out_file, existing, separators=(',', ':'))
                    fetched_routes += 1
                    status = f"✅ fixed {sum(1 for l in existing if l is not None)}/{len(existing)} legs"
                    if route_failed:
                        status += f" ({route_failed} still failed)"
                    print(status)
                    continue
                except (json.JSONDecodeError, OSError):
                    pass  # fall through to full re-fetch
            else:
                skipped_routes += 1
                continue

        n_legs = len(stops) - 1
        print(f"  [{i:3d}/{total_routes}] {route_id:<40} {n_legs} legs … ", end="", flush=True)

        if args.dry_run:
            print("(dry run)")
            fetched_routes += 1
            continue

        legs = []
        route_failed = 0
        for j in range(n_legs):
            leg = osrm_leg(stops[j], stops[j + 1])
            if leg:
                legs.append(leg)
            else:
                legs.append(None)
                route_failed += 1
            total_legs += 1
            if j < n_legs - 1:
                time.sleep(args.delay)

        failed_legs += route_failed
        atomic_write_json(out_file, legs, separators=(',', ':'))
        fetched_routes += 1

        status = f"✅ {n_legs - route_failed}/{n_legs} legs"
        if route_failed:
            status += f" ({route_failed} failed)"
        print(status)

        if i < total_routes:
            time.sleep(args.delay)

    print()
    print(f"✅ Processed : {fetched_routes} route(s)")
    print(f"⏭️  Skipped   : {skipped_routes} (already present or <2 stops)")
    print(f"⚠️  Failed legs: {failed_legs} / {total_legs}")
    if not args.dry_run:
        total_size = sum(
            os.path.getsize(os.path.join(args.output_dir, f))
            for f in os.listdir(args.output_dir)
            if f.endswith(".json")
        )
        print(f"📦 Total geometry dir size: {total_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
