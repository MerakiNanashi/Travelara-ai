
from __future__ import annotations
import json
from app.schemas import POI
from app.config import settings, GA_cat
from app.providers.provider_class import BaseProvider, make_poi_id

# Geoapify categories → preference keys
with open(GA_cat, 'r', encoding='utf-8') as f:
    GEOAPIFY_CATEGORIES = json.load(f)


class GeoapifyProvider(BaseProvider):

    source = "GA"
    url = "https://api.geoapify.com/v2/places"
    category_map = GEOAPIFY_CATEGORIES
    limit = 499

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
                try:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [0, 0])

                    name = str(props.get("name", "")).strip()

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
                                    popularity_score=min(props.get("datasource", {}).get("raw", {}).get("popularity", 0.5), 1.0 ), # same as rating
                                    opening_hours=props.get("opening_hours", {}),
                                    external_links = [v for v in [
                                                props.get("website"),
                                                props.get("datasource").get("source_ref"), ] if v and str(v).strip()],
                                    rating=props.get("datasource", {}).get("raw", {}).get("rating", 3.5), # always default since doesn't exist most often
                                    address=props.get("formatted", ""),
                                    pincode=props.get("postcode", {}),
                                    source="geoapify",
                                )
                            )
                except Exception as e:
                    print(f"Normalize failed: {e}")
                    print(props)


        return pois