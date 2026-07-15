
from __future__ import annotations

import hdbscan
import numpy as np

from src.shared.schemas import POI, StructuredIntent, _PruningConfig, ClusterScore
from src.shared.utils.calcs import haversine_m, shannon_diversity, normalize
from src.shared.adapters import poi_adapter

class Pruning:

    def __init__(self, config: _PruningConfig, clustered_pois: list[POI], cluster_map: dict):
        self.config = config
        self.clustered_pois = clustered_pois
        self.cluster_map = cluster_map
    
    def _compute_cluster_score(self) -> dict[int, ClusterScore]:
        clusters = poi_adapter.group_by_cluster(self.clustered_pois)

        protected_ids = {
            p.id
            for p in poi_adapter.sort_by_utility(self.clustered_pois) \
            [: self.config.protected_top_n]
        }

        cluster_scores: dict[int, ClusterScore] = {}

        for cluster_id, members in clusters.items():
            scores = [
                p.utility.raw
                for p in members
                if p.utility is not None
            ] or [0.0]

            score_sum = float(np.sum(scores))
            score_max = float(np.max(scores))
            score_p90 = float(np.percentile(scores, 90))
            score_avg = score_sum / len(members)

            cluster_scores[cluster_id] = ClusterScore(
                size=len(members),
                sum_score=score_sum,
                max_score=score_max,
                p90_score=score_p90,
                score_avg=score_avg,
                diversity=shannon_diversity(members),
                protected=any(p.id in protected_ids for p in members),
                survival_score=0.0,  # computed after normalization
            )

        self.cluster_scores = cluster_scores

        return cluster_scores
    
    def _calc_cluster_score(self) -> dict[int, ClusterScore]:
        norm_sum = normalize({
            cid: c.sum_score
            for cid, c in self.cluster_scores.items()
        })
        norm_max = normalize({
            cid: c.max_score
            for cid, c in self.cluster_scores.items()
        })
        norm_p90 = normalize({
            cid: c.p90_score
            for cid, c in self.cluster_scores.items()
        })
        norm_avg = normalize({
            cid: c.score_avg
            for cid, c in self.cluster_scores.items()
        })

        quality_weight = 1.0 - self.config.diversity_weight

        for cid, cluster in self.cluster_scores.items():

            # replace with config weights
            quality_component = (
                0.40 * norm_sum[cid]
                + 0.25 * norm_max[cid]
                + 0.25 * norm_p90[cid]
                + 0.10 * norm_avg[cid]
            )

            cluster.survival_score = (
                quality_weight * quality_component
                + self.config.diversity_weight * cluster.diversity
            )

        return dict(
            sorted(
                self.cluster_scores.items(),
                key=lambda item: item[1].survival_score,
                reverse=True,
                )
        )

    def select_cluster(self) ->   tuple[list[POI], 
                                  dict[int, ClusterScore],]:
        
        _ = self._compute_cluster_score()
        ranked_clusters = self._calc_cluster_score()

        survival_scores = [
            c.survival_score
            for c in ranked_clusters.values()
        ]

        threshold = np.percentile(
            survival_scores,
            self.config.pruning_percentile,
        )

        selected_clusters = {
            cid: cluster
            for cid, cluster in ranked_clusters.items()
            if cluster.protected or cluster.survival_score >= threshold
        }

        selected_cids = set(selected_clusters)

        # Keep POIs in surviving clusters; require wiki_and_media for enrichment
        selected_pois = [
            poi for poi in self.clustered_pois
            if self.cluster_map[poi.id] in selected_cids
            and poi.wiki_and_media
        ]
        return (selected_pois, selected_clusters)