
from __future__ import annotations

from src.shared.schemas import POI
from src.retreival.provider_class import BaseProvider
from src.retreival.internals import make_poi_id

class FoursquareProvider(BaseProvider):

    def build_request(self,
                      key,
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
                "Authorization": f"Bearer {key}",
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
                poi_id = make_poi_id("FS", place.get("fsq_place_id", name))
                lat = place.get("latitude", 0)
                lon = place.get("longitude", 0)
                tags = [c.get("name", "") for c in place.get("categories", [])[:5]]
                popularity = min(place.get("popularity", 0.5), 1.0)
                rating = place.get("rating", 7.0) / 10 * 5
                opening_hours = {"display": place.get("hours", {}).get("display", "")} if place.get("hours") else {}
                address = place.get("location", {}).get("formatted_address", "")
                pincode = place.get("location", {}).get("postcode", "")
                distance = place.get("distance")
                external_links = [link for link in 
                                  [*(place.get("social_media") or {}).values(), 
                                    place.get("website")] if link and str(link).strip()]

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
                            distance_m=distance,
                        )
                )
        return pois
