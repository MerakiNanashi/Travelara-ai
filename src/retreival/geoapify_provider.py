
from __future__ import annotations

from src.shared.schemas import POI
from src.retreival.provider_class import BaseProvider
from src.retreival.internals import make_poi_id

class GeoapifyProvider(BaseProvider):

    def build_request(self,
                      key,
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
                "apiKey": key,
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
                    raw = props.get("datasource", {}).get("raw", {})
                    coords = feat.get("geometry", {}).get("coordinates", [0, 0])

                    # Required
                    poi_id = make_poi_id("GA", str(props.get("place_id", "")))
                    name = str(props.get("name", "")).strip()

                    if not name:
                        continue

                    lat = coords[1]
                    lon = coords[0]

                    # Optional
                    tags = props.get("categories", [])[:5]
                    popularity = min(raw.get("popularity", 0.5), 1.0)
                    rating = raw.get("rating", 3.5)
                    opening_hours = props.get("opening_hours", {})
                    address = props.get("formatted", "")
                    pincode = props.get("postcode", "")
                    distance = props.get("distance")
                    wiki = props.get("wiki_and_media", {})

                    external_links = [
                        link
                        for link in (
                            props.get("website"),
                            props.get("datasource", {}).get("source_ref"),
                        )
                        if link and str(link).strip()
                    ]

                    pois.append(
                                self.create_poi(
                                    id=poi_id,
                                    name=name,
                                    lat=lat,
                                    lon=lon,
                                    category=common_category,
                                    tags=tags,
                                    popularity_score=popularity,
                                    rating=rating,
                                    opening_hours=opening_hours,
                                    address=address,
                                    pincode=pincode,
                                    external_links=external_links,
                                    wiki_and_media=wiki,
                                    distance_m=distance
                                )
                            )
                except Exception as e:
                    print(f"Normalize failed: {e}")
                    print(props)


        return pois