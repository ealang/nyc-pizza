#!/usr/bin/env python3
"""Build per-station headway summaries from MTA GTFS.

Input:  .cache/ (unzipped MTA subway GTFS)
        subway-stations-clean.geojson (map station points)
Output: subway-headways.json  { stationName: { day: { "route dir": {band: minutes} } } }

Rerun when refreshing schedules: download new GTFS zip into .cache/, unzip, run.
"""
import csv, json, math, statistics
from collections import defaultdict

CACHE = ".cache"
# Time bands (hours, local): label -> (start, end)
BANDS = [("6a-10a", 6, 10), ("10a-4p", 10, 16), ("4p-8p", 16, 20), ("8p-12a", 20, 24), ("12a-6a", 0, 6)]
DAYS = ["Weekday", "Saturday", "Sunday"]

# --- service_id -> day bucket ---
svc_day = {}
with open(f"{CACHE}/calendar.txt") as f:
    for r in csv.DictReader(f):
        sid = r["service_id"]
        if r["saturday"] == "1": svc_day[sid] = "Saturday"
        elif r["sunday"] == "1": svc_day[sid] = "Sunday"
        elif r["monday"] == "1" or r["wednesday"] == "1": svc_day[sid] = "Weekday"

# --- trips: trip_id -> (route, direction, day) ---
trips = {}
with open(f"{CACHE}/trips.txt") as f:
    for r in csv.DictReader(f):
        day = svc_day.get(r["service_id"])
        if day: trips[r["trip_id"]] = (r["route_id"], r["direction_id"], day)

# --- stops: child stop_id -> parent, parent -> (name, lat, lon) ---
parent_of, parents = {}, {}
with open(f"{CACHE}/stops.txt") as f:
    for r in csv.DictReader(f):
        if r["location_type"] == "1":
            parents[r["stop_id"]] = (r["stop_name"], float(r["stop_lat"]), float(r["stop_lon"]))
        elif r["parent_station"]:
            parent_of[r["stop_id"]] = r["parent_station"]

# --- collect departure times per (parent, route, dir, day) ---
deps = defaultdict(list)
with open(f"{CACHE}/stop_times.txt") as f:
    for r in csv.DictReader(f):
        t = trips.get(r["trip_id"])
        if not t: continue
        parent = parent_of.get(r["stop_id"])
        if not parent: continue
        route, direction, day = t
        h, m, s = r["departure_time"].split(":")
        mins = (int(h) % 24) * 60 + int(m)
        deps[(parent, route, direction, day)].append(mins)

# --- headway per band (median gap between sorted departures) ---
def band_headways(times):
    out = {}
    for label, start, end in BANDS:
        ts = sorted(t for t in times if start * 60 <= t < end * 60)
        if len(ts) < 3: continue
        gaps = [b - a for a, b in zip(ts, ts[1:]) if 0 < b - a < 120]
        if gaps: out[label] = round(statistics.median(gaps))
    return out

summary = defaultdict(lambda: defaultdict(dict))  # parent -> day -> "route|dir" -> bands
for (parent, route, direction, day), times in deps.items():
    bands = band_headways(times)
    if bands: summary[parent][day][f"{route}|{direction}"] = bands

# --- match GTFS parents to our map stations by proximity ---
stations = json.load(open("subway-stations-clean.geojson"))
def dist_m(lat1, lon1, lat2, lon2):
    return math.hypot((lat1 - lat2) * 111320, (lon1 - lon2) * 111320 * math.cos(math.radians(lat1)))

out = {}
matched = 0
for feat in stations["features"]:
    lon, lat = feat["geometry"]["coordinates"]
    name = feat["properties"]["name"]
    # merge all GTFS parent stations within 120m (station complexes)
    merged = defaultdict(dict)
    hit = False
    for pid, (pname, plat, plon) in parents.items():
        if dist_m(lat, lon, plat, plon) < 120 and pid in summary:
            hit = True
            for day, routes in summary[pid].items():
                merged[day].update(routes)
    if hit:
        matched += 1
        out[name] = {d: merged[d] for d in DAYS if d in merged}

json.dump(out, open("subway-headways.json", "w"), separators=(",", ":"))
print(f"matched {matched}/{len(stations['features'])} stations; wrote subway-headways.json")
