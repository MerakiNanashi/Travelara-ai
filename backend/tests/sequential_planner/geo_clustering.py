from helper import measure_latency
import json
import math
from itertools import combinations

with open(
    r"C:\Users\kuchbhe\Desktop\Travelara-ai\output\serpapi_results\Paris_20260511_013337.json",
    "r",
    encoding="utf-8"
) as f:
    results = json.load(f)


def parse_input(results):
    """
    Extract POIs with latitude and longitude.
    """

    pois = []
    for query in results:
        for item in query:
            try:
                pois.append({
                    "category": query,
                    "name": item.get("title"),
                    "place_id": item.get("place_id"),
                    "lat": float(item["gps_coordinates"]["latitude"]),
                    "lon": float(item["gps_coordinates"]["longitude"]),
                    "raw": item
                })
            except (KeyError, TypeError, ValueError):
                continue

    return pois


def calculate_haversine(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in KM.
    """

    R = 6371  # Earth radius in KM

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def compute_pairwise_distances(pois):
    """
    Compute and store pairwise haversine distances.
    """

    pairwise_distances = {}

    for poi1, poi2 in combinations(pois, 2):

        distance = calculate_haversine(
            poi1["lat"],
            poi1["lon"],
            poi2["lat"],
            poi2["lon"]
        )

        key = (poi1["place_id"], poi2["place_id"])

        pairwise_distances[key] = round(distance, 2)

    return pairwise_distances


def filter_pois_by_haversine(pois, center_lat, center_lon, radius_km):
    """
    Return POIs within radius_km of center point.
    """

    filtered = []

    for poi in pois:

        distance = calculate_haversine(
            center_lat,
            center_lon,
            poi["lat"],
            poi["lon"]
        )

        if distance <= radius_km:
            poi["distance_from_center_km"] = round(distance, 2)
            filtered.append(poi)

    return filtered


# Example usage
pois = parse_input(results)

# Pairwise distance matrix
pairwise_distances = compute_pairwise_distances(pois)

print(f"Computed {len(pairwise_distances)} pairwise distances")

# Example preview
for pair, distance in list(pairwise_distances.items())[:5]:
    print(pair, "->", distance, "km")


# Radius filtering example
nearby_pois = filter_pois_by_haversine(
    pois,
    center_lat=48.8566,
    center_lon=2.3522,
    radius_km=5
)

print(f"\nFound {len(nearby_pois)} nearby POIs")