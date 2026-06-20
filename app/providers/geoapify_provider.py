
from __future__ import annotations
from app.schemas import POI
from app.config import settings
from app.providers.provider_class import BaseProvider, make_poi_id

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
                                id=make_poi_id("GA", str(props.get("place_id", name))),
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