"""
Quick inspection tool for espoo_ice_cream_routes.json.
Run:  python view_routes.py
      python view_routes.py 11_123_22   # drill into a specific route
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("metro_ice_cream_routes.json", encoding="utf-8") as f:
    routes = json.load(f)

# ── Summary table ─────────────────────────────────────────────────────────────
print(f"{'DAY':<12} {'ROUTE ID':<22} {'STOPS':>5}  {'SEASON'}")
print("-" * 65)
for r in sorted(routes, key=lambda x: (x["weekday"] or "", x["route_id"] or "")):
    day    = (r["weekday"] or "?").capitalize()
    rid    = r["route_id"] or "unnamed"
    stops  = len(r["stops"])
    sched  = r["stops"][0]["schedules"] if r["stops"] else []
    season = f"{sched[0]['date']} → {sched[-1]['date']}" if sched else "no dates"
    print(f"{day:<12} {rid:<22} {stops:>5}  {season}")

print(f"\nTotal: {len(routes)} routes, {sum(len(r['stops']) for r in routes)} stops")

# ── Drill into a specific route ───────────────────────────────────────────────
query = sys.argv[1] if len(sys.argv) > 1 else None
if query:
    match = next((r for r in routes if query in (r["route_id"] or "")), None)
    if not match:
        print(f"\nRoute '{query}' not found.")
    else:
        r = match
        sched = r["stops"][0]["schedules"] if r["stops"] else []
        print(f"\nRoute:  {r['route_id']}  ({r['weekday']})  file={r['file']}")
        dates = [s["date"] for s in sched]
        print(f"Dates:  {', '.join(dates[:4])} … ({len(dates)} visits)")
        print(f"Stops ({len(r['stops'])}):")
        for s in r["stops"]:
            coords = f"({s['lat']:.5f}, {s['lon']:.5f})" if s["lat"] else "no coords"
            time   = s["schedules"][0]["time"] if s["schedules"] else "?"
            print(f"  {time}  {s['zip']}  {s['name']:<45}  {coords}")
