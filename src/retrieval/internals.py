from __future__ import annotations
from rapidfuzz import fuzz
import csv
from pathlib import Path
import h3

from src.shared.schemas import POI, Preference, PreferenceType


def make_poi_id(source, id):
    return f"{source}_{id}"

def _get_top_preferences(prefs: dict[str, float],
                         threshold: float = 0.3,
                         limit: int = 4) -> list[str]:

    sorted_cats = sorted(prefs.items(), key=lambda x: x[1], reverse=True)
    return [k for k, v in sorted_cats if v >= threshold][:limit]

def get_categorymap(prefs: dict[str, float],
                     category_map: dict) -> dict[str, list[str]]:

    top_cats = _get_top_preferences(prefs, 0.5, 100)
    selected_map = {category: category_map.get(category, []) for category in top_cats}
    return selected_map

def preferences_to_legacy(
    preferences: list[Preference],
) -> dict[str, float]:
    """
    Convert sparse Preference objects into a category->weight mapping.

    - Ignore subjective preferences.
    - Ignore preferences without a category.
    - For duplicate categories, keep the highest weight.
    """

    category_weights: dict[str, float] = {}

    for pref in preferences:
        if (
            pref.type != PreferenceType.OBJECTIVE
            or pref.category is None
        ):
            continue

        category_weights[pref.category] = max(
            category_weights.get(pref.category, 0.0),
            pref.weight,
        )

    return category_weights

# Input: threshold - decides the threshold for resolution/grid cells, output: resultion closest to threshold
def _h3_resolution_for(threshold_m: float) -> int:
    """Pick the H3 resolution whose average cell edge is closest to
    threshold_m, so 'same cell or adjacent' roughly matches 'within
    threshold_m'. H3 edge lengths shrink ~2.9x per resolution step."""
    # Approximate avg edge length (m) per H3 resolution, res 6-12
    EDGE_LENGTHS_M = {6: 3229, 7: 1220, 8: 461, 9: 174, 10: 65.9, 11: 24.9, 12: 9.4}
    return min(EDGE_LENGTHS_M, key=lambda res: abs(EDGE_LENGTHS_M[res] - threshold_m))

# Input: Raw POIs (After GA/FS), Threshold_m for resolution, Output: Undropped POIs
# Function: dedup based on fuzzy name & lat, lon
def deduplicate(
    pois: list[POI],
    threshold_m: float = 100.0,
    name_match_threshold: int = 90
) -> list[POI]:
    """
    Dedupe same-name POIs that are spatially close, using H3 cell
    bucketing instead of pairwise distance checks. Each POI is hashed to
    a cell; candidates are only ever compared against others in the same
    or adjacent cell — O(1) average per POI, not O(n) or O(n^2).
    """
    resolution = _h3_resolution_for(threshold_m)

    # cell_id -> {normalized_name: POI already kept in that cell}
    # Type cast
    buckets: dict[str, dict[str, POI]] = {}
    kept: list[POI] = []
    dropped_by_category: dict[str, int] = {}

    for poi in pois:
        # Read(POI)
        norm_name = poi.normalized_name
        lat, lon = poi.get_coordinates
        category = poi.category

        # Logic
        cell = h3.latlng_to_cell(lat, lon, resolution)
        is_duplicate = False
        # Compare only against candidates in this cell and neighboring cells
        for neighbor_cell in h3.grid_disk(cell, 1):
            for existing in buckets.get(neighbor_cell, []):
                score = fuzz.token_set_ratio(
                    norm_name,
                    existing.name.lower().strip(),
                )
                if score >= name_match_threshold:
                    is_duplicate = True
                    break
            if is_duplicate:
                break
        if is_duplicate:
            dropped_by_category[category] = (
                dropped_by_category.get(category, 0) + 1
            )
            continue
        buckets.setdefault(cell, []).append(poi)
        kept.append(poi)

    return kept

# Input: filepath, Output: list of dicts with keys: name, lat, lon, population
# Parse file into travelsable output
def _parse_geocode_file(filepath: str) -> list[dict]:
    cleaned = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            try:
                cleaned.append(
                    {
                        "name": str(row[1]).strip().lower(),
                        "lat": float(row[4]),
                        "lon": float(row[5]),
                        "population": int(row[14]) if row[14] else 0,
                    }
                )
            except Exception:
                print("parse_geocode_file failed")
                continue
    return cleaned

# Input: destination, geonames_file, Output: lat, lon -> Gets exported to providers/provider_class.py
# Func - resolve lat & lon for destination
def retrieve_latlon(
    destination: str,
    geonames_file: Path,
) -> tuple[float, float]:

    data = _parse_geocode_file(geonames_file)
    matches = []
    for row in data:
        score = fuzz.partial_ratio(
            destination.lower(),
            row["name"]
        )
        if score >= 70:
            matches.append((score, row))
    if not matches:
        raise ValueError(f"Could not resolve destination: {destination}")
    matches.sort(
        key=lambda x: (
            x[0],
            x[1]["population"]
        ),
        reverse=True,
    )
    best = matches[0][1]
    return best["lat"], best["lon"]