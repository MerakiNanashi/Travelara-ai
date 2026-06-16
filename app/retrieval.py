"""
Retrieval service: fetches candidate POIs from Geoapify (geocoding + places)
and Foursquare (enriched venue data).
"""
from __future__ import annotations
import httpx
import hashlib
from rapidfuzz import fuzz
import csv
from pathlib import Path
from app.schemas import POI, StructuredIntent, Preferences
from app.config import settings, latlon_path


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
        "tourism.attraction"
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


def _make_poi_id(source: str, raw_id: str) -> str:
    return hashlib.md5(f"{source}:{raw_id}".encode()).hexdigest()[:16]


def _preference_score(category_key: str, prefs: Preferences) -> float:
    return getattr(prefs, category_key, 0.3)

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



async def fetch_geoapify_pois(
    lat: float,
    lon: float,
    prefs: Preferences,
    radius_m: int = 8000,
    limit: int = 100,
) -> list[POI]:
    """Fetch places from Geoapify Places API based on preference weights."""
    # Select top categories by preference score
    pref_dict = prefs.model_dump()
    sorted_cats = sorted(pref_dict.items(), key=lambda x: x[1], reverse=True)
    top_cats = [k for k, v in sorted_cats if v >= 0.3][:4]

    categories_param = ",".join(
        cat for key in top_cats
        for cat in GEOAPIFY_CATEGORIES.get(key, [])
    )

    pois: list[POI] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://api.geoapify.com/v2/places",
            params={
                "categories": categories_param,
                "filter": f"circle:{lon},{lat},{radius_m}",
                "bias": f"proximity:{lon},{lat}",
                "limit": limit,
                "apiKey": settings.geoapify_api_key,
            }
        )
        r.raise_for_status()

    for feat in r.json().get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [0, 0])

        name = props.get("name", "").strip()
        if not name:
            continue

        raw_cats = props.get("categories", [])
        category_key = _infer_category_key(raw_cats)

        pois.append(POI(
            id=_make_poi_id("geoapify", props.get("place_id", name)),
            name=name,
            lat=coords[1],
            lon=coords[0],
            category=category_key,
            tags=raw_cats[:5],
            popularity_score=min(props.get("datasource", {}).get("raw", {}).get("popularity", 0.5), 1.0),
            avg_duration_minutes=_estimate_duration(category_key),
            estimated_cost_usd=_estimate_cost(category_key),
            rating=props.get("datasource", {}).get("raw", {}).get("rating", 3.5),
            address=props.get("formatted", ""),
            source="geoapify",
        ))

    return pois


def _infer_category_key(raw_cats: list[str]) -> str:
    raw = " ".join(raw_cats).lower()
    if "museum" in raw or "art_gallery" in raw:
        return "museums"
    if "restaurant" in raw or "cafe" in raw or "food" in raw or "catering" in raw:
        return "food"
    if "nightclub" in raw or "bar" in raw:
        return "nightlife"
    if "park" in raw or "nature" in raw or "forest" in raw:
        return "nature"
    if "shopping" in raw or "mall" in raw or "commercial" in raw:
        return "shopping"
    if "theatre" in raw or "culture" in raw:
        return "arts"
    if "castle" in raw or "memorial" in raw or "sight" in raw:
        return "history"
    if "spa" in raw or "wellness" in raw or "fitness" in raw:
        return "wellness"
    return "general"


# ─── Foursquare ───────────────────────────────────────────────────────────────

async def fetch_foursquare_pois(
    lat: float,
    lon: float,
    prefs: Preferences,
    radius_m: int = 8000,
    limit: int = 50,
) -> list[POI]:
    """Fetch venues from Foursquare Places API."""
    pref_dict = prefs.model_dump()
    sorted_cats = sorted(pref_dict.items(), key=lambda x: x[1], reverse=True)
    top_cats = [k for k, v in sorted_cats if v >= 0.3][:3]

    # Build category list
    fs_cats = list({
        cat_id
        for key in top_cats
        for cat_id in FOURSQUARE_CATEGORIES.get(key, [])
    })
    categories_param = ",".join(fs_cats[:6])

    pois: list[POI] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://places-api.foursquare.com/places/search",
            params={
                "ll": f"{lat},{lon}",
                "radius": radius_m,
                "categories": categories_param,
                "limit": limit,
            },
            headers={
                "Authorization": f"Bearer {settings.foursquare_api_key}",
                "X-Places-Api-Version": "2025-06-17",
                "Accept": "application/json",
            }
        )

        print("FS Status:", r.status_code)
        print("FS Response:", r.text[:1000])

        r.raise_for_status()

    for place in r.json().get("results", []):
        name = place.get("name", "").strip()
        if not name:
            continue

        geo = place.get("geocodes", {}).get("main", {})
        fs_cats_raw = place.get("categories", [])
        category_key = _infer_category_key_fs(fs_cats_raw)

        pois.append(POI(
            id=_make_poi_id("foursquare", place.get("fsq_id", name)),
            name=name,
            lat=geo.get("latitude", lat),
            lon=geo.get("longitude", lon),
            category=category_key,
            tags=[c.get("name", "") for c in fs_cats_raw[:5]],
            popularity_score=min(place.get("popularity", 0.5), 1.0),
            avg_duration_minutes=_estimate_duration(category_key),
            estimated_cost_usd=_price_to_cost(place.get("price", 2), category_key),
            rating=place.get("rating", 7.0) / 10.0 * 5.0,  # normalize 0-10 → 0-5
            address=place.get("location", {}).get("formatted_address", ""),
            source="foursquare",
            opening_hours={"display": place.get("hours", {}).get("display", "")} if place.get("hours") else {},
        ))

    return pois


def _infer_category_key_fs(cats: list[dict]) -> str:
    if not cats:
        return "general"
    names = " ".join(c.get("name", "") for c in cats).lower()
    if "museum" in names or "gallery" in names:
        return "museums"
    if "restaurant" in names or "café" in names or "cafe" in names or "food" in names:
        return "food"
    if "bar" in names or "nightclub" in names or "lounge" in names:
        return "nightlife"
    if "park" in names or "garden" in names or "nature" in names:
        return "nature"
    if "shop" in names or "mall" in names or "market" in names:
        return "shopping"
    if "theater" in names or "theatre" in names or "arts" in names:
        return "arts"
    if "historic" in names or "monument" in names or "shrine" in names or "temple" in names:
        return "history"
    if "spa" in names or "gym" in names or "wellness" in names:
        return "wellness"
    return "general"


def _estimate_duration(category: str) -> int:
    durations = {
        "museums": 120,
        "food": 75,
        "nightlife": 120,
        "nature": 90,
        "shopping": 90,
        "arts": 100,
        "history": 90,
        "wellness": 90,
        "general": 60,
    }
    return durations.get(category, 60)


def _estimate_cost(category: str) -> float:
    costs = {
        "museums": 15.0,
        "food": 20.0,
        "nightlife": 30.0,
        "nature": 0.0,
        "shopping": 50.0,
        "arts": 25.0,
        "history": 10.0,
        "wellness": 40.0,
        "general": 5.0,
    }
    return costs.get(category, 5.0)


def _price_to_cost(price_tier: int, category: str) -> float:
    """Convert Foursquare price tier (1–4) to USD estimate."""
    base = _estimate_cost(category)
    multiplier = {1: 0.5, 2: 1.0, 3: 2.0, 4: 3.5}.get(price_tier, 1.0)
    return base * multiplier


# ─── Combined retrieval ───────────────────────────────────────────────────────

async def retrieve_candidates(intent: StructuredIntent) -> tuple[list[POI], float, float]:
    """
    Main retrieval entry point.
    Returns (pois, center_lat, center_lon).
    Merges Geoapify + Foursquare results, deduplicates by proximity.
    """
    lat, lon = retrieve_latlon(
        f"{intent.destination}",
        latlon_path
    )

    radius_m = int(intent.constraints.walking_limit_km * 1500)  # generous radius

    geo_pois, fs_pois = [], []

    if settings.geoapify_api_key:
        try:
            geo_pois = await fetch_geoapify_pois(lat, lon, intent.preferences, radius_m)
        except Exception as e:
            print(f"[Geoapify] retrieval error: {e}")

    if settings.foursquare_api_key:
        try:
            fs_pois = await fetch_foursquare_pois(lat, lon, intent.preferences, radius_m)
        except Exception as e:
            print(f"[Foursquare] retrieval error: {e}")

    all_pois = _deduplicate(geo_pois + fs_pois)

    # Filter must-visit (always include)
    must_names = {m.lower() for m in intent.constraints.must_visit}
    must_pois = [p for p in all_pois if any(m in p.name.lower() for m in must_names)]
    rest = [p for p in all_pois if p not in must_pois]

    # Filter avoids
    avoid_cats = {a.lower() for a in intent.constraints.avoid}
    rest = [p for p in rest if p.category.lower() not in avoid_cats]

    return must_pois + rest, lat, lon


def _deduplicate(pois: list[POI], threshold_m: float = 100.0) -> list[POI]:
    """Remove near-duplicate POIs (same name or very close coordinates)."""
    seen_names: set[str] = set()
    result: list[POI] = []

    for poi in pois:
        norm_name = poi.name.lower().strip()
        if norm_name in seen_names:
            continue
        # Check coordinate proximity to existing result
        too_close = any(
            _haversine(poi.lat, poi.lon, r.lat, r.lon) < threshold_m
            for r in result
        )
        if too_close:
            continue
        seen_names.add(norm_name)
        result.append(poi)

    return result


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon points."""
    import math
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))
