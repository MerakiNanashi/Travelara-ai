from __future__ import annotations

from app.clustering import Clustering
from app.schemas import (
    Stage,
    PlanningState,
    Cluster,
    ClusteringConfig,
)


class ClusteringStage(Stage):

    def __init__(
        self,
        config: ClusteringConfig | None = None,
    ):
        self.config = config or ClusteringConfig()

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        clustering = Clustering(
            intent=state.intent,
            pois=state.raw_pois,
            config=self.config,
        )

        result = clustering.select_clusters()

        state.scored_pois = clustering.scored_pois
        state.clustered_pois = clustering.clustered_pois
        state.cluster_selection = result

        state.clusters = {
            cluster.cluster_id: Cluster(
                cluster_id=cluster.cluster_id,
                size=cluster.size,
                density=cluster.density,
                sum_score=cluster.sum_score,
                max_score=cluster.max_score,
                p90_score=cluster.p90_score,
                survival_score=cluster.survival_score,
                protected=cluster.protected,
                poi_ids=[
                    poi.id
                    for poi in clustering.clustered_pois
                    if poi.cluster_id == cluster.cluster_id
                ],
            )
            for cluster in result.selected_clusters
        }

        state.artifacts.cluster_map = result.cluster_map

        return state