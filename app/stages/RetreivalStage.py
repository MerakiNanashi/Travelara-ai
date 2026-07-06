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
            "lat": state.anchor.lat,
            "lon": state.anchor.lon,
            "prefs": state.intent.preferences,
            "radius_m": state.constraints.radius_m,
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

        state.candidate_pois = pois

        return state