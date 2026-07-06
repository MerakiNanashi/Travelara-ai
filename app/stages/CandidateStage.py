from __future__ import annotations

from app.schemas import PlanningState, Stage
from app.reranker.score import CandidateScorer


class CandidateStage(Stage):

    def __init__(
        self,
        scorer: CandidateScorer | None = None,
    ):
        self.scorer = scorer or CandidateScorer()

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        result = await self.scorer.score(
            clustering=state.cluster_selection,
            intent=state.intent,
        )

        state.candidate_selection = result
        state.planned_pois = [
            poi
            for day in result.days
            for poi in day.pois
        ]

        state.anchor_ids = [
            day.anchor.id
            for day in result.days
        ]

        return state