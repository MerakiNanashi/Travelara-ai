"""
Retrieval service: fetches candidate POIs from providers.
Current Providers:
- Geoapify (geocoding + places)
- Foursquare (enriched venue data).
"""

from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
import httpx
from app.schemas import POI, Preferences


def make_poi_id(source, id):
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