from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from app.schemas import ClusteredPOI, AnchorPOI, AnchorScore
from app.utils.calcs import haversine_m, normalize


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
        sigma_m: float = 500.0,
        neighbor_radius_m: float = 400.0,
    ):
        self.sigma_m = sigma_m
        self.neighbor_radius_m = neighbor_radius_m

    def score(
        self,
        pois: list[ClusteredPOI],
        cluster_map: dict[str, int],
    ) -> None:
        if not pois:
            return

        clusters: dict[int, list[ClusteredPOI]] = defaultdict(list)

        for poi in pois:
            clusters[cluster_map[poi.id]].append(poi)

        utility = normalize({
            poi.id: poi.utility.raw if poi.utility else 0.0
            for poi in pois
        })

        for members in clusters.values():

            if len(members) == 1:
                self._score_singleton(
                    members[0],
                    utility,
                )
                continue

            self._score_cluster(
                members,
                utility,
            )

    def _score_singleton(
        self,
        poi: ClusteredPOI,
        utility: dict[str, float],
    ) -> None:
        anchor = poi.anchor

        anchor.representative = 1.0
        anchor.expansion = 1.0
        anchor.connectivity = 1.0
        anchor.importance = poi.popularity_score or 0.0

        anchor.overall = (
            0.30 * anchor.semantic
            + 0.25 * utility[poi.id]
            + 0.20 * anchor.representative
            + 0.15 * anchor.expansion
            + 0.05 * anchor.connectivity
            + 0.05 * anchor.importance
        )

    def _score_cluster(
        self,
        members: list[ClusteredPOI],
        utility: dict[str, float],
    ) -> list[AnchorPOI]:

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

        anchors: list[AnchorPOI] = []

        for poi in members:
            normalized_utility = utility[poi.id]

            score = AnchorScore(
                semantic=poi.utility.semantic,
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
                AnchorPOI(
                    **poi.model_dump(),
                    anchor=score,
                )
            )

        return anchors