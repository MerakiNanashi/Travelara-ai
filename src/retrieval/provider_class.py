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
import json
# From Candidate:POI, Intent:Preference
from src.shared.schemas import POI, Preference,_ProviderConfig
from src.retrieval.internals import get_categorymap, preferences_to_legacy


class BaseProvider(ABC):

    def __init__(self, 
                 config: _ProviderConfig,
                 key):
        self.source = config.source
        self.key = key
        self.taxonomy_path = config.taxonomy_path
        self.url = config.url
        self.limit = config.limit
        self.category_map = self._get_map()

    def _get_map(self) -> dict:
        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            category_map = json.load(f)
        return category_map

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
    
    def create_poi(self, **kwargs) -> POI:
        kwargs["source"] = self.source
        return POI(**kwargs)
    
    async def fetch_category(self,
                             client: httpx.AsyncClient,
                             common_category: str,
                             provider_categories: list[str],
                             lat: float,
                             lon: float,
                             radius_m: int,):

        params, headers = self.build_request(
            key=self.key,
            provider_categories=provider_categories,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            limit=self.limit,
        )

        r = await client.get(
            self.url,
            params=params,
            headers=headers,
        )

        if r.status_code != 200:
            print(r.text)
            r.raise_for_status()

        return common_category, r.json()

    async def fetch(self,
                    lat: float,
                    lon: float,
                    category_map: dict[str, list[str]],
                    timeout: float = 20.0,
                    radius_m: int = 8000,
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

    # Main orchestrator of provider module
    async def retrieve(self,
                       lat: float,
                       lon: float,
                       prefs: list[Preference],
                       radius_m: int = 8000,
                       debug: bool = False) -> list[POI]:

        prefs_legacy = preferences_to_legacy(prefs)

        selected_categories = get_categorymap(
                prefs_legacy,
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