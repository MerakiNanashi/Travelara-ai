from __future__ import annotations

import asyncio

from app.providers import deduplicate, BaseProvider
from app.schemas import Stage, PlanningState

# Copy and update, no inplace updation
class RetrievalStage(Stage):

    def __init__(
        self,
        providers: list[BaseProvider],
    ):
        self.providers = providers

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        request = {
            "lat": state.raw_pois.lat,
            "lon": state.raw_pois.lon,
            "prefs": state.intent.preferences,
            "radius_m": state.intent.constraints.walking_limit_km,
        }
        

        results = await asyncio.gather(
            *[
                provider.retrieve(**request)
                for provider in self.providers
            ]
        )

        pois = [
            poi
            for provider_result in results
            for poi in provider_result
        ]

        pois = deduplicate(pois)

        state.raw_pois = pois

        return state