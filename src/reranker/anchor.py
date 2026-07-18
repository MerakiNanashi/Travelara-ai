from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from src.shared.schemas import POI, AnchorScore
from src.shared.utils.calcs import haversine_m, normalize
from src.shared.adapters import poi_adapter

class AnchorScorer:
    """
    Computes anchor quality metrics for clustered POIs.

    Responsibilities
    ----------------
    • Representative score
    • Expansion score
    • Connectivity score
    • Popularity score
    • Overall anchor score

    Assumes:
        - Semantic scores are already computed.
        - Utility scores already exist.
        - Cluster map is available.

    Mutates only:
        poi.anchor
    """

    def __init__(
        self,
        pois: list[POI],
        sigma_m: float = 500.0,
        neighbor_radius_m: float = 400.0,
    ):
        self.pois = pois
        self.sigma_m = sigma_m
        self.neighbor_radius_m = neighbor_radius_m

    def score(
        self,
    ) -> tuple[list[POI], dict[int, list[POI]]]:
        if not self.pois:
            return
        clusters: dict[int, list[POI]] = poi_adapter.group_by_cluster(self.pois)

        utility = normalize({
            poi.id: poi.utility.raw if poi.utility else 0.0
            for poi in self.pois
        })
        anchors = []
        for members in clusters.values():
            if len(members) == 1:
                anchors.append(
                self._score_singleton(
                    members[0],
                    utility,
                )
                )
                continue

            anchors.extend(
                self._score_cluster(
                    members,
                    utility,
                )
            )

        return (anchors, clusters)
    def _score_singleton(
        self,
        poi: POI,
        utility: dict[str, float],
    ) -> POI:
        semantic = poi.anchor.semantic if poi.anchor else 0.0
        importance = poi.popularity_score or 0.0
        utility_score = utility.get(poi.id, 0.0)

        representative = 1.0
        expansion = 1.0
        connectivity = 1.0

        overall = (
            0.30 * semantic
            + 0.25 * utility_score
            + 0.20 * representative
            + 0.15 * expansion
            + 0.05 * connectivity
            + 0.05 * importance
        )

        poi.anchor = AnchorScore(
            semantic=semantic,
            representative=representative,
            expansion=expansion,
            connectivity=connectivity,
            importance=importance,
            overall=overall,
        )

        return poi

    def _score_cluster(
        self,
        members: list[POI],
        utility: dict[str, float],
    ) -> list[POI]:

        centroid_lat = np.mean([p.lat for p in members])
        centroid_lon = np.mean([p.lon for p in members])

        distances_to_centroid = {
            p.id: haversine_m(
                centroid_lat,
                centroid_lon,
                p.lat,
                p.lon,
            )
            for p in members
        }

        max_centroid_distance = max(
            distances_to_centroid.values()
        ) + 1e-6

        representative = {}
        expansion = {}
        connectivity = {}
        importance = {}

        distance_matrix = {}

        for i, poi in enumerate(members):

            representative[poi.id] = (
                1.0
                - distances_to_centroid[poi.id] / max_centroid_distance
            )

            expansion_score = 0.0
            connectivity_score = 0

            for j in range(i + 1, len(members)):

                other = members[j]

                d = haversine_m(
                    poi.lat,
                    poi.lon,
                    other.lat,
                    other.lon,
                )

                distance_matrix[(poi.id, other.id)] = d
                distance_matrix[(other.id, poi.id)] = d

            for other in members:

                if poi.id == other.id:
                    continue

                d = distance_matrix[(poi.id, other.id)]

                u = utility[other.id]

                expansion_score += (
                    u * math.exp(-d / self.sigma_m)
                )

                if (
                    d <= self.neighbor_radius_m
                    and u >= 0.6
                ):
                    connectivity_score += 1

            expansion[poi.id] = expansion_score
            connectivity[poi.id] = connectivity_score
            importance[poi.id] = poi.popularity_score or 0.0

        representative = normalize(representative)
        expansion = normalize(expansion)
        connectivity = normalize(connectivity)
        importance = normalize(importance)

        anchors: list[POI] = []

        for poi in members:
            normalized_utility = utility[poi.id]

            score = AnchorScore(
                semantic=poi.anchor.semantic,
                representative=representative[poi.id],
                expansion=expansion[poi.id],
                connectivity=connectivity[poi.id],
                importance=importance[poi.id],
                overall=(
                    0.30 * poi.utility.semantic
                    + 0.25 * normalized_utility
                    + 0.20 * representative[poi.id]
                    + 0.15 * expansion[poi.id]
                    + 0.05 * connectivity[poi.id]
                    + 0.05 * importance[poi.id]
                ),
            )

            anchors.append(
                POI(
                    **poi.model_dump(exclude={"anchor"}),
                    anchor=score,
                )
            )

        return anchors