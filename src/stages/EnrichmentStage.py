from __future__ import annotations

from src.shared.schemas import (
    PlanningState,
    Stage,
    StageContext,
    _WikipediaConfig,
)

from .BaseStage import BaseStage
from src.enrichment.description import Enrichment


class EnrichmentStage(BaseStage):

    def __init__(self, context: StageContext):
        super().__init__(context=context)

        self.debugger = context.debugger
        self.config = context.config["stage4"]

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        enrichment = Enrichment(
            pois=state.selected_pois,
            wikidata_url=self.config["wiki"]["api_url"],
            config=_WikipediaConfig(**self.config["wiki"]),
        )

        state.enriched_pois = await enrichment.enrich()

        self.debugger.report(
            Stage.ENRICHMENT,
            {
                "selected_pois": len(state.selected_pois),
                "enriched": sum(
                    poi.wiki_enrichment is not None
                    for poi in state.enriched_pois
                ),
            },
        )

        self.debugger.save_stage(
            Stage.ENRICHMENT,
            4,
            state,
        )

        return state