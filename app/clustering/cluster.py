"""
Clustering service:
- POI utility scoring
- HDBSCAN spatial clustering with noise reassignment
- Cluster scoring and percentile pruning
"""
from __future__ import annotations

import math
from collections import defaultdict

import hdbscan
import numpy as np

from app.clustering.filter import Filter
from app.schemas import POI, StructuredIntent, ScoredPOI, ClusteredPOI, ClusterScore, ClusteringConfig, ClusterSelectionResult
from app.adapters import poi_adapter
from app.utils.calcs import haversine_m, shannon_diversity, normalize

class Clustering:
    def __init__(self, intent: StructuredIntent, pois: list[POI], config: ClusteringConfig):
        self.intent = intent
        self.pois = pois # RAW POIS 
        self.config = config
        self.scored_pois: list[ScoredPOI] = [] #- With Score -> score_all_pois updates to ScoredPOI
        self.clustered_pois: list[ClusteredPOI] = []

        # self.min_cluster_size: int
        # self.min_samples: int = 2
        # self.protected_top_n: int = 50
        # self.diversity_weight: float = 0.15
        # self.pruning_percentile: float = 60.0


    # ---------------------------------------------------------------------------
    # POI utility scoring
    # ---------------------------------------------------------------------------

    def score_all_pois(self) -> list[ScoredPOI]:
        """Run Filter scoring on all POIs and attach QualityScore to each."""
        scores = Filter(self.pois, self.intent).score_filter()
        scored_pois = []
        for poi, score in zip(self.pois, scores):
                scored_pois.append(
                    ScoredPOI(**poi.model_dump(),
                              utility=score))
        self.scored_pois = scored_pois
        return poi_adapter.sort_by_utility(self.scored_pois)
    
    # ---------------------------------------------------------------------------
    # Spatial clustering
    # ---------------------------------------------------------------------------

    def cluster_pois(
        self
    ) -> dict[str, int]:
        """Return a mapping of poi.id → cluster_id using HDBSCAN."""

        # Case when pois retreived less than min_cluster_suze * min_samples
        required = max(self.config.min_cluster_size * self.config.min_samples, 10)
        if len(self.scored_pois) < required:
            return {p.id: 0 for p in self.scored_pois}

        # Convert to raidan & build hdbscan 
        # To do: 
        # 1. Benchmark different clustering algos - measure 
        # 2. Benchmark selected algo / top 3 algo on various cases such as sparsity, dense networks, etc.
        coords = np.radians([[p.lat, p.lon] for p in self.scored_pois])
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.min_cluster_size,
            min_samples=self.config.min_samples,
            metric="haversine",
        )
        labels = clusterer.fit_predict(coords)

        cluster_map = {self.scored_pois[i].id: int(labels[i]) for i in range(len(self.scored_pois))}
        reassigned_map = self._reassign_noise(cluster_map)

        self.clustered_pois = [
            ClusteredPOI(
                **poi.model_dump(),
                cluster_id=reassigned_map[poi.id],
            )
            for poi in self.scored_pois
        ]
        return reassigned_map # Need to return map for later use

    def _reassign_noise(
        self,
        cluster_map: dict[str, int],
    ) -> dict[str, int]:
        """Assign HDBSCAN noise points (label -1) to their nearest cluster."""
        # retreive all clusters except -1 ie. noise
        clustered = [p for p in self.scored_pois if cluster_map[p.id] != -1]
        # assign -1 into cluster 0 -> default noise cluster
        if not clustered:
            return {p.id: 0 for p in self.scored_pois}
        # Assign rest of the noise to closest neighbor
        for poi in self.scored_pois:
            if cluster_map[poi.id] == -1:
                nearest = min(
                    clustered,
                    key=lambda c: haversine_m(poi.lat, poi.lon, c.lat, c.lon),
                )
                cluster_map[poi.id] = cluster_map[nearest.id]
        return cluster_map

    def compute_cluster_scores(self) -> list[ClusterScore]:
        """
        Score every cluster on four quality metrics plus a category-diversity
        metric, and return all ranked clusters.

        Pruning is performed later in `select_clusters`.
        """
        clusters = poi_adapter.group_by_cluster(self.clustered_pois)

        protected_poi_ids = {
            p.id
            for p in poi_adapter.sort_by_utility(self.clustered_pois)[
                : self.config.protected_top_n
            ]
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
            density = score_sum / len(members)

            cluster_scores[cluster_id] = ClusterScore(
                cluster_id=cluster_id,
                sum_score=score_sum,
                max_score=score_max,
                p90_score=score_p90,
                size=len(members),
                density=density,
                category_diversity=shannon_diversity(members),
                protected=any(p.id in protected_poi_ids for p in members),
                survival_score=0.0,  # computed after normalization
            )

        norm_sum = normalize({
            cid: c.sum_score
            for cid, c in cluster_scores.items()
        })
        norm_max = normalize({
            cid: c.max_score
            for cid, c in cluster_scores.items()
        })
        norm_p90 = normalize({
            cid: c.p90_score
            for cid, c in cluster_scores.items()
        })
        norm_density = normalize({
            cid: c.density
            for cid, c in cluster_scores.items()
        })

        quality_weight = 1.0 - self.config.diversity_weight

        for cid, cluster in cluster_scores.items():
            quality_component = (
                0.40 * norm_sum[cid]
                + 0.25 * norm_max[cid]
                + 0.25 * norm_p90[cid]
                + 0.10 * norm_density[cid]
            )

            cluster.survival_score = (
                quality_weight * quality_component
                + self.config.diversity_weight * cluster.category_diversity
            )

        return sorted(
            cluster_scores.values(),
            key=lambda c: c.survival_score,
            reverse=True,
        )

    def select_clusters(self) -> ClusterSelectionResult:
        """
        Full cluster selection pipeline:
        score_all_pois → cluster_pois → compute_cluster_scores → percentile prune

        Returns:
            selected_pois   – POIs belonging to surviving clusters (with wiki_and_media)
            selected_clusters – cluster dicts that survived pruning
            cluster_map     – full poi.id → cluster_id mapping
        """
        scored_pois = self.score_all_pois()
        cluster_map = self.cluster_pois()

        ranked_clusters = self.compute_cluster_scores()

        survival_scores = [c.survival_score for c in ranked_clusters]
        threshold = np.percentile(survival_scores, self.config.pruning_percentile)

        selected_clusters = [
            c for c in ranked_clusters
            if c.protected or c.survival_score >= threshold
        ]

        selected_cids = {c.cluster_id for c in selected_clusters}

        # Keep POIs in surviving clusters; require wiki_and_media for enrichment
        selected_pois = [
            poi for poi in scored_pois
            if cluster_map[poi.id] in selected_cids
            and poi.wiki_and_media
        ]

        return ClusterSelectionResult(
            selected_pois=selected_pois,
            selected_clusters=selected_clusters,
            cluster_map=cluster_map,
            threshold=float(threshold),
        )