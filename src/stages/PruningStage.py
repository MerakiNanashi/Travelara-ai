from __future__ import annotations

from src.shared.schemas import (
    PlanningState,
    Stage,
    StageContext,
    _FilterConfig,
    _ClusteringConfig,
    _PruningConfig,
)

from .BaseStage import BaseStage
from src.pruning import Pruning, Clustering, Filter


class PruningStage(BaseStage):

    def __init__(self, context: StageContext):
        super().__init__(context=context)

        self.debugger = context.debugger
        self.config = context.config["stage3"]

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:
        
        filter = Filter(intent=state.intent,
                        pois=state.raw_pois,
                        config=_FilterConfig(**self.config["filter"]),)
        
        sorted_pois = filter.score_pois()
        state.scored_pois = sorted_pois

        clustering = Clustering(intent=state.intent,
                                scored_pois=sorted_pois,
                                config=_ClusteringConfig(**self.config["clustering"]))
        (cluster_map, clustered_pois) = clustering.cluster_pois()
        state.clustered_pois = clustered_pois
        state.artifacts.cluster_map = cluster_map

        pruning = Pruning(
            clustered_pois=clustered_pois,
            cluster_map=cluster_map,
            config=_PruningConfig(**self.config["pruning"]),
        )

        (
            selected_pois,
            selected_clusters,
        ) = pruning.select_cluster()

        state.selected_pois = selected_pois
        state.artifacts.selected_clusters = selected_clusters

        self.debugger.report(
            Stage.PRUNING,
            {
                "scored_pois": len(state.scored_pois),
                "clustered_pois": len(state.clustered_pois),
                "selected_pois": len(state.selected_pois),
                "clusters": len(state.artifacts.selected_clusters),
            },
        )
        self.debugger.save_stage(
            Stage.PRUNING,
            5,
            state,
        )

        return state