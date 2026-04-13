"""
enrich_routing.py — Add road-following geometry to ice cream truck routes.

Queries the OSRM public routing API for each route's full stop sequence,
replacing straight-line connections with actual street paths.

Output: metro_ice_cream_routes.json is updated in-place (atomic write).
Each stop gains a `path_to_next` field: [[lat, lon], ...] waypoints to
the NEXT stop along real roads, or null for the last stop.

Usage:
    python enrich_routing.py [--dry-run] [--delay 0.25]

Options:
    --dry-run      Parse and report without writing output
    --delay N      Seconds to sleep between API requests (default 0.25)
    --input FILE   Input JSON file (default metro_ice_cream_routes.json)
    --output FILE  Output JSON file (default same as input, in-place)

Notes:
    • Uses the OSRM public demo server (router.project-osrm.org).
      For production / high-volume use, run your own OSRM instance.
    • ~152 routes → ~152 HTTP requests → roughly 45 seconds at default delay.
    • Re-running is safe: already-enriched stops are skipped unless --force.
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


# ── OSRM query ────────────────────────────────────────────────────────────────

def osrm_route(stops: list[dict]) -> list[list[list[float]]] | None:
    """
    Query OSRM for a route through all stops in order.
    Returns a list of leg geometries, each a list of [lat, lon] pairs.
    Returns None on failure.
    """
    if len(stops) < 2:
        return None

    coords = ";".join(f"{s['lon']},{s['lat']}" for s in stops)
    url = (
        f"{OSRM_BASE}/{coords}"
        f"?overview=full&geometries=geojson&steps=false"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "jatskiauto-map/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return None

    if data.get("code") != "Ok":
        return None

    legs = data["routes"][0]["legs"]
    result = []
    for leg in legs:
        # GeoJSON coords are [lon, lat] — flip to [lat, lon] for Leaflet
        coords_raw = leg["geometry"]["coordinates"]
        result.append([[c[1], c[0]] for c in coords_raw])
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich routes with OSRM road geometry")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output")
    parser.add_argument("--force", action="store_true", help="Re-enrich even if already done")
    parser.add_argument("--delay", type=float, default=0.25, help="Sleep between API calls (sec)")
    parser.add_argument("--input",  default="metro_ice_cream_routes.json")
    parser.add_argument("--output", default=None, help="Output file (default: same as input)")
    args = parser.parse_args()

    output_file = args.output or args.input

    print("🍦 Jätskiauto Route Enrichment (OSRM)")
    print(f"   Input  : {args.input}")
    print(f"   Output : {output_file}")
    print(f"   Delay  : {args.delay}s between requests")
    if args.dry_run:
        print("   Mode   : DRY RUN (no writes)")
    print()

    with open(args.input, encoding="utf-8") as f:
        routes = json.load(f)

    if not isinstance(routes, list):
        routes = list(routes.values())

    total      = len(routes)
    enriched   = 0
    skipped    = 0
    failed     = 0

    for i, route in enumerate(routes, 1):
        stops = route.get("stops", [])
        if len(stops) < 2:
            skipped += 1
            continue

        # Check if already enriched (unless --force)
        already_done = any(s.get("path_to_next") is not None for s in stops[:-1])
        if already_done and not args.force:
            skipped += 1
            continue

        rid = route.get("route_id", f"#{i}")
        print(f"  [{i:3d}/{total}] {rid:<40} ", end="", flush=True)

        legs = osrm_route(stops)

        if legs and len(legs) == len(stops) - 1:
            for j, leg_coords in enumerate(legs):
                stops[j]["path_to_next"] = leg_coords
            stops[-1]["path_to_next"] = None
            enriched += 1
            total_pts = sum(len(l) for l in legs)
            print(f"✅ {len(legs)} legs, {total_pts} pts")
        else:
            # Fall back: keep straight lines (path_to_next = None)
            for s in stops:
                s["path_to_next"] = None
            failed += 1
            print("⚠️  OSRM failed → straight lines")

        if i < total:
            time.sleep(args.delay)

    print()
    print(f"✅ Enriched : {enriched} routes")
    print(f"⏭️  Skipped  : {skipped} (already done or <2 stops)")
    print(f"⚠️  Failed   : {failed} (straight lines kept)")

    if not args.dry_run:
        atomic_write_json(output_file, routes, ensure_ascii=False, indent=None)
        print(f"💾 Saved to {output_file}")
    else:
        print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
