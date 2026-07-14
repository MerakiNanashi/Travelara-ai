from __future__ import annotations

import asyncio

from src.shared.schemas import PlanningState, Stage, StageContext
from .BaseStage import BaseStage
from src.retreival import get_params, build_providers, deduplicate

class RetreivalStage(BaseStage):

    def __init__(self, context: StageContext):
        super().__init__(
            context=context
        )

        self.debugger = context.debugger
        self.settings = context.settings
        self.config = context.config['stage2']
        self.provider_config = context.config['stage2']['providers']
       

    async def run(self,
            state:PlanningState
            ) -> PlanningState:
            
        try:
            providers = build_providers(config=self.config,
                                        settings=self.settings)
            lat, lon, radius_m, prefs = get_params(intent=state.intent, config=self.config)
            tasks = [
                provider.retrieve(
                    lat=lat,
                    lon=lon,
                    prefs=prefs,
                    radius_m=radius_m,
                )
                for provider in providers.values()
            ]

            results = await asyncio.gather(*tasks)

            pois = [
                poi
                for provider_result in results
                for poi in provider_result
            ]

            dedup_pois = deduplicate(pois=pois)

            kept = set(map(id, dedup_pois))
            discarded_dups = [poi for poi in pois if id(poi) not in kept]

            state.raw_pois = dedup_pois
            state.discarded_dups = discarded_dups

            self.debugger.report(Stage.RETRIEVAL, state.model_dump())
            self.debugger.save_stage(Stage.RETRIEVAL, 2, state)

            return state

        except Exception as e:
            raise e
