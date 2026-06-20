"""
Retrieval service: fetches candidate POIs from Geoapify (geocoding + places)
and Foursquare (enriched venue data).
"""
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
import httpx
import hashlib
from rapidfuzz import fuzz
import csv
from pathlib import Path
from app.schemas import POI, StructuredIntent, Preferences
from app.config import settings, latlon_path, in_latlon_path


# ─── Category mappings ────────────────────────────────────────────────────────

# Geoapify categories → preference keys
GEOAPIFY_CATEGORIES = {
    "museums": [
        "entertainment.museum",
        "entertainment.culture",
        "entertainment.culture.gallery",
    ],

    "food": [
        "catering",
        "catering.restaurant",
        "catering.cafe",
        "catering.fast_food",
    ],

    "nightlife": [
        "catering.bar",
        "catering.pub",
        "catering",
    ],

    "nature": [
        "leisure.park",
        "leisure.park.garden",
        "natural",
        "natural.forest",
        "natural.water",
    ],

    "shopping": [
        "commercial",
        "commercial.shopping_mall",
        "commercial.marketplace",
        "commercial.food_and_drink",
    ],

    "arts": [
        "entertainment.culture",
        "entertainment.culture.theatre",
        "entertainment.culture.gallery",
        "entertainment.culture.arts_centre",
    ],

    "history": [
        "tourism",
        "tourism.attraction",
        "tourism.sights",
        "tourism.sights.castle",
        "tourism.sights.memorial",
        "tourism.sights.monastery",
        "heritage",
    ],

    "wellness": [
        "leisure.spa",
        "sport.fitness",
        "sport.fitness.gym",
    ],
}


# Foursquare category IDs → preference keys
FOURSQUARE_CATEGORIES = {
    "museums":   ["10027", "10000"],   # Museum, Arts & Entertainment
    "food":      ["13000", "13032"],   # Food, Restaurant
    "nightlife": ["10032", "13003"],   # Nightlife, Bar
    "nature":    ["16000", "16032"],   # Outdoors, Park
    "shopping":  ["17000", "17069"],   # Retail
    "arts":      ["10024", "10004"],   # Theater, Concert
    "history":   ["16010", "16011"],   # Historic Site, Monument
    "wellness":  ["18000", "18021"],   # Spa, Gym
}


# ─── Geoapify ─────────────────────────────────────────────────────────────────

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


def _make_poi_id(source, id):
    return f"{source}_{id}"


def _get_top_preferences(prefs: Preferences,
                         threshold: float = 0.3,
                         limit: int = 4) -> list[str]:

    pref_dict = prefs.model_dump()
    sorted_cats = sorted(pref_dict.items(), key=lambda x: x[1], reverse=True)

    return [k for k, v in sorted_cats if v >= threshold][:limit]


def _get_categorymap(prefs: Preferences,
                     category_map: dict) -> dict[str, list[str]]:

    top_cats = _get_top_preferences(prefs, 0.5, 100)
    selected_map = {category: category_map.get(category, []) for category in top_cats}
    return selected_map


class BaseProvider(ABC):

    source: str
    category_map: dict[str, list[str]]
    url: str

    @abstractmethod
    def build_request(self,
                      provider_categories: list[str],
                      lat: float,
                      lon: float,
                      radius_m: int,
                      limit: int) -> tuple[dict, dict]:
        pass

    @abstractmethod
    def normalize(self,
                  results: dict[str, dict]) -> list[POI]:
        pass

    async def fetch_category(self,
                             client: httpx.AsyncClient,
                             common_category: str,
                             provider_categories: list[str],
                             lat: float,
                             lon: float,
                             radius_m: int,
                             limit: int):

        params, headers = self.build_request(
            provider_categories=provider_categories,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            limit=limit,
        )

        r = await client.get(
            self.url,
            params=params,
            headers=headers,
        )

        r.raise_for_status()

        return common_category, r.json()

    async def fetch(self,
                    lat: float,
                    lon: float,
                    category_map: dict[str, list[str]],
                    timeout: float = 20.0,
                    radius_m: int = 8000,
                    limit: int = 100,
                    debug: bool = False) -> dict[str, dict]:

        async with httpx.AsyncClient(timeout=timeout) as client:

            tasks = [
                self.fetch_category(
                    client=client,
                    common_category=common_category,
                    provider_categories=provider_categories,
                    lat=lat,
                    lon=lon,
                    radius_m=radius_m,
                    limit=limit,
                )
                for common_category, provider_categories in category_map.items()
            ]

            responses = await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        result = {}

        for response in responses:

            if isinstance(response, Exception):
                print(f"FAILED: {response}")
                continue

            common_category, payload = response
            result[common_category] = payload

            if debug:
                print(f"Processed: {common_category}")

        return result

    async def retrieve(self,
                       lat: float,
                       lon: float,
                       prefs: Preferences,
                       radius_m: int = 8000,
                       debug: bool = False) -> list[POI]:
        
        selected_categories = _get_categorymap(
                prefs,
                self.category_map,
            )
  
        results = await self.fetch(
            lat=lat,
            lon=lon,
            category_map=selected_categories,
            radius_m=radius_m,
            debug=debug
        )

        return self.normalize(results)


class GeoapifyProvider(BaseProvider):

    source = "GA"
    url = "https://api.geoapify.com/v2/places"
    category_map = GEOAPIFY_CATEGORIES

    def build_request(self,
                      provider_categories: list[str],
                      lat: float,
                      lon: float,
                      radius_m: int,
                      limit: int):

        return (
            {
                "categories": ",".join(provider_categories),
                "filter": f"circle:{lon},{lat},{radius_m}",
                "bias": f"proximity:{lon},{lat}",
                "limit": limit,
                "apiKey": settings.geoapify_api_key,
            },
            {},
        )

    def normalize(self,
                  results: dict[str, dict]) -> list[POI]:

        pois = []

        for common_category, payload in results.items():

            for feat in payload.get("features", []):

                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [0, 0])

                name = props.get("name", "").strip()

                if not name:
                    continue

                pois.append(
                            POI(
                                id=_make_poi_id("GA", str(props.get("place_id", name))),
                                name=name,
                                lat=coords[1],
                                lon=coords[0],
                                category=common_category,
                                tags=props.get("categories", [])[:5],
                                popularity_score=min(props.get("datasource", {}).get("raw", {}).get("popularity", 0.5), 1.0 ),
                                rating=props.get("datasource", {}).get("raw", {}).get("rating", 3.5),
                                address=props.get("formatted", ""),
                                source="geoapify",
                            )
                        )

        return pois


class FoursquareProvider(BaseProvider):

    source = "FS"
    url = "https://places-api.foursquare.com/places/search"
    category_map = FOURSQUARE_CATEGORIES

    def build_request(self,
                      provider_categories: list[str],
                      lat: float,
                      lon: float,
                      radius_m: int,
                      limit: int):

        return (
            {
                "ll": f"{lat},{lon}",
                "radius": radius_m,
                "categories": ",".join(provider_categories),
                "limit": limit,
            },
            {
                "Authorization": f"Bearer {settings.foursquare_api_key}",
                "X-Places-Api-Version": "2025-06-17",
                "Accept": "application/json",
            },
        )

    def normalize(self,
                  results: dict[str, dict]) -> list[POI]:

        pois = []

        for common_category, payload in results.items():

            for place in payload.get("results", []):

                name = place.get("name", "").strip()

                if not name:
                    continue

                geo = place.get("geocodes", {}).get("main", {})

                pois.append(
                        POI(
                            id=_make_poi_id("FS", place.get("fsq_id", name)),
                            name=name,
                            lat=geo.get("latitude", 0),
                            lon=geo.get("longitude", 0),
                            category=common_category,
                            tags=[c.get("name", "") for c in place.get("categories", [])[:5]],
                            popularity_score=min(place.get("popularity", 0.5), 1.0),
                            opening_hours={"display": place.get("hours", {}).get("display", "")} if place.get("hours") else {},
                            rating=place.get("rating", 7.0) / 10 * 5,
                            address=place.get("location", {}).get("formatted_address", ""),
                            source="foursquare",
                        )
                )

        return pois


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


async def run_retreival(source,
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