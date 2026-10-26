#!/usr/bin/env python3
"""Pack Overpass Edmonton data into compact static JSON for the explore page.

Reads the raw .freebuff/tmp/*.out.json extracts and writes ./data/:
  roads-central.json, roads-full.json, pois.json, extras.json
Format is minimized for size; coordinates rounded to 5 decimals (~1 m).
"""
import json, math, os, sys

RAW = ".freebuff/tmp"
DATA = "data"
os.makedirs(DATA, exist_ok=True)

CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary",
           "unclassified", "residential"]

COS_LAT = math.cos(math.radians(53.5))

def seg_len_m(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    dx = (lon2 - lon1) * 111320.0 * COS_LAT
    dy = (lat2 - lat1) * 110540.0
    return math.sqrt(dx * dx + dy * dy)

def round5(v):
    return round(v, 5)

def pack_roads(src_name, out_name):
    raw = json.load(open(os.path.join(RAW, src_name), encoding="utf-8"))
    by_class = {}
    total_by_class = {}
    bbox = [90, 180, -90, -180]  # minLat, minLon, maxLat, maxLon
    for e in raw["elements"]:
        geom = e.get("geometry")
        if not geom or len(geom) < 2:
            continue
        cls = e["tags"]["highway"]
        if cls not in CLASSES:
            continue
        pts_pairs = [[round5(p["lon"]), round5(p["lat"])] for p in geom]
        length = sum(seg_len_m(pts_pairs[i], pts_pairs[i + 1]) for i in range(len(pts_pairs) - 1))
        if length < 15:  # ignore slivers
            continue
        by_class.setdefault(cls, []).append({"i": e["id"], "g": pts_pairs})
        total_by_class[cls] = total_by_class.get(cls, 0.0) + length
        for p in (pts_pairs[0], pts_pairs[-1]):
            bbox[0] = min(bbox[0], p[1])
            bbox[1] = min(bbox[1], p[0])
            bbox[2] = max(bbox[2], p[1])
            bbox[3] = max(bbox[3], p[0])
    counts = {c: len(by_class.get(c, [])) for c in CLASSES if by_class.get(c)}
    payload = {
        "v": 1,
        "bbox": [round5(bbox[1]), round5(bbox[0]), round5(bbox[3]), round5(bbox[2])],  # [w, s, e, n]
        "classes": {c: {"n": counts[c], "lenM": round(total_by_class[c])}
                    for c in CLASSES if c in counts},
        "ways": {c: by_class[c] for c in counts},
    }
    blob = json.dumps(payload, separators=(",", ":"))
    with open(os.path.join(DATA, out_name), "w", encoding="utf-8") as f:
        f.write(blob)
    print(f"{out_name}: {len(blob)//1024} KB, classes: {counts}, "
          f"total len: {int(sum(total_by_class.values())/1000)} km")

def poi_kind(tags):
    t = tags
    if "tourism" in t:
        k = t["tourism"]
        if k in ("museum",): return "museum"
        if k in ("artwork",): return "art"
        if k in ("monument",): return "monument"
        return "attraction"
    if "historic" in t: return "historic"
    if "amenity" in t:
        k = t["amenity"]
        if k in ("hospital",): return "hospital"
        if k in ("university", "college"): return "university"
        if k == "library": return "library"
        if k == "marketplace": return "market"
    if "leisure" in t:
        k = t["leisure"]
        if k == "stadium": return "stadium"
        if k in ("sports_centre", "recreation_ground"): return "sports"
    return None

def pack_pois():
    raw = json.load(open(os.path.join(RAW, "q_poi.out.json"), encoding="utf-8"))
    seen, out = set(), []
    for e in raw["elements"]:
        tags = e.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        kind = poi_kind(tags)
        if not kind:
            continue
        if e["type"] == "node":
            lo, la = round5(e["lon"]), round5(e["lat"])
        else:
            geom = e.get("geometry")
            if not geom or len(geom) < 3:
                continue
            lo = round5(sum(p["lon"] for p in geom) / len(geom))
            la = round5(sum(p["lat"] for p in geom) / len(geom))
        dedupe = (name, kind, round(la, 3), round(lo, 3))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({"n": name, "k": kind, "lo": lo, "la": la})
    blob = json.dumps({"v": 1, "pois": out}, separators=(",", ":"), ensure_ascii=False)
    open(os.path.join(DATA, "pois.json"), "w", encoding="utf-8").write(blob)
    from collections import Counter
    print(f"pois.json: {len(blob)//1024} KB, {len(out)} POIs: {Counter(p['k'] for p in out)}")

def pack_extras():
    raw = json.load(open(os.path.join(RAW, "q_extra.out.json"), encoding="utf-8"))
    rivers, hoods = [], []
    river_path = os.path.join(RAW, "river.out.json")
    if os.path.exists(river_path):
        rraw = json.load(open(river_path, encoding="utf-8"))
        for e in rraw["elements"]:
            if e["type"] == "way" and e.get("geometry") and len(e["geometry"]) >= 2:
                rivers.append([[round5(p["lon"]), round5(p["lat"])] for p in e["geometry"]])
    for e in raw["elements"]:
        tags = e.get("tags") or {}
        if e["type"] == "way":
            geom = e.get("geometry") or []
            if len(geom) < 2:
                continue
            if tags.get("waterway") == "river" and "Saskatchewan" in tags.get("name", ""):
                rivers.append([[round5(p["lon"]), round5(p["lat"])] for p in geom])
        elif e["type"] == "node" and "name" in tags:
            hoods.append({"n": tags["name"], "lo": round5(e["lon"]), "la": round5(e["lat"])})
    blob = json.dumps({"v": 1, "river": rivers, "hoods": hoods},
                      separators=(",", ":"), ensure_ascii=False)
    open(os.path.join(DATA, "extras.json"), "w", encoding="utf-8").write(blob)
    print(f"extras.json: {len(blob)//1024} KB, river segs: {len(rivers)}, hoods: {len(hoods)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and "extras" in sys.argv[1]:
        pack_extras()
    else:
        pack_roads("roads_central.json", "roads-central.json")
        pack_roads("q_geom_full.out.json", "roads-full.json")
        pack_pois()
        pack_extras()
