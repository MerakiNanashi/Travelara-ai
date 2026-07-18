from __future__ import annotations

from src.shared.schemas import (
    PlanningState,
    Stage,
    StageContext,
)

from .BaseStage import BaseStage
from src.builder.builder import CandidatePoolBuilder


class BuildStage(BaseStage):

    def __init__(
        self,
        context: StageContext,
    ):
        super().__init__(context=context)

        self.debugger = context.debugger
        self.config = context.config["stage6"]

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        builder = CandidatePoolBuilder(
            target_per_day=self.config["target_per_day"],
            expansion_radius_m=self.config["expansion_radius_m"],
            diversity_weight=self.config["diversity_weight"],
            distance_decay_m=self.config["distance_decay_m"],
        )

        candidate_selection = builder.select(
            pois=state.ranked_pois,
            selected_clusters=state.artifacts.selected_clusters,
            cluster_map=state.artifacts.cluster_map_ptoid,
            days=state.intent.days.value,
        )

        state.artifacts.candidate_selection = candidate_selection

        state.candidate_pois = [
            poi
            for cluster in candidate_selection
            for poi in cluster.pois
        ]

        self.debugger.report(
            Stage.BUILD,
            {
                "candidate_days": len(candidate_selection),
                "candidate_pois": len(state.candidate_pois),
            },
        )

        self.debugger.save_stage(
            Stage.BUILD,
            6,
            state,
        )

        return state