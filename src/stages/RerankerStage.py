from __future__ import annotations

import torch

from src.shared.schemas import (
    PlanningState,
    Stage,
    StageContext,
)

from .BaseStage import BaseStage

from src.reranker.semantic import SemanticScorer
from src.reranker.anchor import AnchorScorer


class RerankerStage(BaseStage):

    def __init__(
        self,
        context: StageContext,
    ):
        super().__init__(context=context)

        self.debugger = context.debugger
        self.config = context.config["stage5"]

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:
        
        if torch.cuda.is_available():
            device = "cuda"
        else: 
            device = "cpu"

        # -----------------------------
        # Semantic Scoring
        # -----------------------------
        semantic = SemanticScorer(
            pois=state.enriched_pois,
            intent=state.intent,
            model_name=self.config["semantic"]["model"],
            batch_size=self.config["semantic"]["batch_size"],
            device=device
        )

        semantic_pois = semantic.score()

        # -----------------------------
        # Anchor Scoring
        # -----------------------------
        anchor = AnchorScorer(
            pois=semantic_pois,
            sigma_m=self.config["anchor"]["sigma_m"],
            neighbor_radius_m=self.config["anchor"]["neighbor_radius_m"],
        )

        ranked_pois, cluster_map_idtop = anchor.score()

        state.ranked_pois = ranked_pois
        state.artifacts.cluster_map_idtop = cluster_map_idtop

        self.debugger.report(
            Stage.RERANKER,
            {
                "semantic_pois": len(semantic_pois),
                "ranked_pois": len(state.ranked_pois),
            },
        )

        self.debugger.save_stage(
            Stage.RERANKER,
            5,
            state,
        )

        return state