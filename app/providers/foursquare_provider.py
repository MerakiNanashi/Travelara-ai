
from __future__ import annotations
import json
from app.schemas import POI
from app.config import settings, FS_cat
from app.providers.provider_class import BaseProvider, make_poi_id

# Foursquare category IDs → preference keys
with open(FS_cat, 'r', encoding='utf-8') as f:
    FOURSQUARE_CATEGORIES = json.load(f)


class FoursquareProvider(BaseProvider):

    source = "FS"
    url = "https://places-api.foursquare.com/places/search"
    category_map = FOURSQUARE_CATEGORIES
    limit = 49

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

                name = str(place.get("name", "")).strip()

                if not name:
                    continue

                geo = place.get("geocodes", {}).get("main", {})

                pois.append(
                        POI(
                            id=make_poi_id("FS", place.get("fsq_id", name)),
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
