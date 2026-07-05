"""
Retrieval service: fetches candidate POIs from providers.
Current Providers:
- Geoapify (geocoding + places)
- Foursquare (enriched venue data).
"""

from __future__ import annotations
import asyncio
from datetime import datetime
from abc import ABC, abstractmethod
import httpx
from app.schemas import POI, Preference_List, Preference, PreferenceType
from pathlib import Path
import os
import json


def preferences_to_legacy(
    preferences: list[Preference],
) -> Preference_List:
    """
    Convert the new sparse Preference list into the legacy dense
    Preferences object expected by the retrieval layer.

    Rules:
    - Ignore subjective preferences.
    - Ignore preferences without a category.
    - For duplicate categories, keep the highest weight.
    """

    data = Preference_List().model_dump()

    for pref in preferences:
        if (
            pref.type != PreferenceType.OBJECTIVE
            or pref.category is None
        ):
            continue

        category = pref.category
        data[category] = max(
            data.get(category, 0.0),
            pref.weight,
        )

    return Preference_List(**data)

def make_poi_id(source, id):
    return f"{source}_{id}"


def _get_top_preferences(prefs: Preference_List,
                         threshold: float = 0.3,
                         limit: int = 4) -> list[str]:

    pref_dict = prefs.model_dump()
    sorted_cats = sorted(pref_dict.items(), key=lambda x: x[1], reverse=True)

    return [k for k, v in sorted_cats if v >= threshold][:limit]


def _get_categorymap(prefs: Preference_List,
                     category_map: dict) -> dict[str, list[str]]:

    top_cats = _get_top_preferences(prefs, 0.5, 100)
    selected_map = {category: category_map.get(category, []) for category in top_cats}
    return selected_map


class BaseProvider(ABC):

    source: str
    category_map: dict[str, list[str]]
    url: str
    limit: int

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
                             radius_m: int,):

        params, headers = self.build_request(
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
    
    # shift this to utils
    def _save(self,
            raw_result: dict[str, dict],
            run_id: str,
            save_dir: Path,):
        now = datetime.now()
        os.makedirs(save_dir, exist_ok=True)
        filename = save_dir / f"{self.source}_{run_id}_rawresult_{now:%Y%m%d_%H%M%S}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
            raw_result,
            f,
            indent=2,
            default=str,
            ensure_ascii=False,
        )

    async def retrieve(self,
                       lat: float,
                       lon: float,
                       prefs: list[Preference],
                       radius_m: int = 8000,
                       debug: bool = False) -> list[POI]:

        prefs_legacy = preferences_to_legacy(prefs)

        selected_categories = _get_categorymap(
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

        self._save(results, "1234", Path("RawResult")) # Should change to a more standard saving method/folder, also need to pass id through

        return self.normalize(results)