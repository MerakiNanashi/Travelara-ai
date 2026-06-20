from __future__ import annotations
from rapidfuzz import fuzz
import csv
from pathlib import Path

from app.schemas import POI, StructuredIntent
from app.config import latlon_path, in_latlon_path
from app.providers.foursquare_provider import FoursquareProvider
from app.providers.geoapify_provider import GeoapifyProvider

def parse_geocode_file(filepath: str):
    cleaned = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")

        for row in reader:
            try:
                cleaned.append(
                    {
                        "name": row[1].strip().lower(),
                        "lat": float(row[4]),
                        "lon": float(row[5]),
                        "population": int(row[14]) if row[14] else 0,
                    }
                )
            except Exception:
                continue

    return cleaned


def retrieve_latlon(
    destination: str,
    geonames_file: Path,
) -> tuple[float, float]:

    data = parse_geocode_file(geonames_file)

    matches = []

    for row in data:
        score = fuzz.partial_ratio(
            destination.lower(),
            row["name"]
        )

        if score >= 70:
            matches.append((score, row))

    if not matches:
        raise ValueError(
            f"Could not resolve destination: {destination}"
        )

    matches.sort(
        key=lambda x: (
            x[0],
            x[1]["population"]
        ),
        reverse=True,
    )

    best = matches[0][1]

    return best["lat"], best["lon"]

PROVIDERS = {
    "GA": GeoapifyProvider(),
    "FS": FoursquareProvider(),
}


def _deduplicate(pois: list[POI],
                 threshold_m: float = 100.0,
                 debug: bool = False) -> list[POI]:

    seen_names = set()
    result = []
    dropped = {}

    for poi in pois:

        norm_name = poi.name.lower().strip()

        if norm_name in seen_names:
            dropped[poi.category] = dropped.get(poi.category, 0) + 1
            continue

        seen_names.add(norm_name)
        result.append(poi)

    if debug:
        print("\n=== DEDUPLICATION ===")
        print(f"Input POIs: {len(pois)}")
        print(f"Output POIs: {len(result)}")
        print(f"Dropped: {sum(dropped.values())}")
        print(f"By Category: {dropped}")

    return result



# Main orchestrator for retrieval
async def run_retrieval(source,
                        intent: StructuredIntent,
                        debug: bool = False):

    lat, lon = retrieve_latlon(
        intent.destination,
        latlon_path if intent.is_international else in_latlon_path
    )

    if debug:
        print("\n=== RETRIEVAL START ===")
        print(f"Provider: {source}")
        print(f"Destination: {intent.destination}")
        print(f"Coordinates: ({lat}, {lon})")
        print(f"Preferences: {intent.preferences.model_dump()}")

    radius_m = int(intent.constraints.walking_limit_km * 1500)

    try:

        raw_pois = await PROVIDERS[source].retrieve(
            lat=lat,
            lon=lon,
            prefs=intent.preferences,
            radius_m=radius_m,
            debug=debug
        )

    except Exception as e:

        print(f"{source} Retrieval error: {e}")
        raw_pois = []

    pois = _deduplicate(raw_pois, debug=debug)

    if debug:
        counts = {}
        for poi in pois:
            counts[poi.category] = counts.get(poi.category, 0) + 1

        print("\n=== AFTER DEDUP ===")
        print(f"Total POIs: {len(pois)}")
        print(counts)

    must_names = {m.lower() for m in intent.constraints.must_visit}
    must_pois = [p for p in pois if any(m in p.name.lower() for m in must_names)]
    rest = [p for p in pois if p not in must_pois]

    if debug:
        print("\n=== MUST VISIT FILTER ===")
        print(f"Must Visit Targets: {intent.constraints.must_visit}")
        print(f"Matched POIs: {len(must_pois)}")

    avoid_cats = {a.lower() for a in intent.constraints.avoid}
    rest = [p for p in rest if p.category.lower() not in avoid_cats]
    before_avoid = len(rest)
    final_pois = must_pois + rest

    if debug:
        print("\n=== AVOID FILTER ===")
        print(f"Avoid Categories: {avoid_cats}")
        print(f"Removed: {before_avoid - len(rest)}")
        counts = {}

        for poi in final_pois:
            counts[poi.category] = counts.get(poi.category, 0 ) + 1

        print("\n=== FINAL RESULT ===")
        print(f"Total POIs: {len(final_pois)}")
        print(f"Must Visit POIs: {len(must_pois)}")
        print(f"Regular POIs: {len(rest)}")
        print(counts)
        print("======================\n")

    return final_pois, lat, lon