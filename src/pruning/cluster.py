"""
Clustering service:
- POI utility scoring
- HDBSCAN spatial clustering with noise reassignment
- Cluster scoring and percentile pruning
"""
from __future__ import annotations

import hdbscan
import numpy as np

from src.shared.schemas import POI, StructuredIntent, _ClusteringConfig
from src.shared.utils.calcs import haversine_m


class Clustering:
    def __init__(self, intent: StructuredIntent, scored_pois: list[POI], config: _ClusteringConfig):
        self.intent = intent
        self.scored_pois = scored_pois
        self.config = config
        self.clustered_pois: list[POI] = []

    def cluster_pois(self) -> tuple[dict[str, int], list[POI]]:
        # Performs clustering using hdbscan/h3 index etc.
        
        # Pre-requisites
        required = max(self.config.min_cluster_size, 1)

        if len(self.scored_pois) < required:
            return {p.id: 0 for p in self.scored_pois}
        
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
            POI(
                **poi.model_dump(exclude={"cluster_id"}),
                cluster_id=reassigned_map[poi.id],
            )
            for poi in self.scored_pois
        ]

        return (reassigned_map, self.clustered_pois)

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
