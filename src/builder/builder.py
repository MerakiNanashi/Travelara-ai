from __future__ import annotations

import math
from collections import Counter, defaultdict

from src.shared.adapters import poi_adapter
from src.shared.schemas import ClusterScore, POI, CandidateSelectionResult
from src.shared.utils.calcs import haversine_m


class CandidatePoolBuilder:
    """
    Builds daily candidate pools around cluster anchors.

    Objectives
    ----------
    • Preserve anchor quality
    • Maximize semantic + utility
    • Encourage category variety
    • Allow neighboring-cluster expansion
    • Keep walking localized
    """

    def __init__(
        self,
        target_per_day: int = 6,
        expansion_radius_m: float = 750.0,
        diversity_weight: float = 0.35,
        distance_decay_m: float = 500.0,
    ):
        self.target_per_day = target_per_day
        self.expansion_radius_m = expansion_radius_m
        self.diversity_weight = diversity_weight
        self.distance_decay_m = distance_decay_m

    def select(
        self,
        pois: list[POI],
        selected_clusters: dict[int, ClusterScore],
        cluster_map: dict[str, int],
        days: int,
    ) -> list[CandidateSelectionResult]:

        by_cluster = poi_adapter.group_by_cluster(pois)

        ranked_clusters = sorted(
            selected_clusters.items(),
            key=lambda c: c[1].survival_score,
            reverse=True,
        )[:days]

        used: set[str] = set()
        result: list[dict] = []

        for cluster_id, cluster in ranked_clusters:

            members = sorted(
                by_cluster.get(cluster_id, []),
                key=lambda p: p.anchor.overall,
                reverse=True,
            )

            if not members:
                continue

            anchor = members[0]
            used.add(anchor.id)

            selected = [anchor]

            self._greedy_fill(
                anchor,
                members[1:],
                selected,
                used,
            )

            if len(selected) < self.target_per_day:

                neighbors = self._neighbor_candidates(
                    anchor,
                    pois,
                    cluster_id,
                    cluster_map,
                    used,
                )

                self._greedy_fill(
                    anchor,
                    neighbors,
                    selected,
                    used,
                )

            result.append(
                CandidateSelectionResult(
                    cluster = cluster,
                    anchor = anchor,
                    pois = selected,)
            )

        return result

    def _neighbor_candidates(
        self,
        anchor: POI,
        pois: list[POI],
        cluster_id: int,
        cluster_map: dict[str, int],
        used: set[str],
    ) -> list[POI]:

        return [
            poi
            for poi in pois
            if poi.id not in used
            and cluster_map[poi.id] != cluster_id
            and haversine_m(
                anchor.lat,
                anchor.lon,
                poi.lat,
                poi.lon,
            ) <= self.expansion_radius_m
        ]

    def _greedy_fill(
        self,
        anchor: POI,
        candidates: list[POI],
        selected: list[POI],
        used: set[str],
    ) -> None:

        remaining = [p for p in candidates if p.id not in used]

        while remaining and len(selected) < self.target_per_day:

            best = max(
                remaining,
                key=lambda poi: self._score(
                    anchor,
                    poi,
                    selected,
                ),
            )

            selected.append(best)
            used.add(best.id)
            remaining.remove(best)

    def _score(
        self,
        anchor: POI,
        poi: POI,
        selected: list[POI],
    ) -> float:

        distance = math.exp(
            -haversine_m(
                anchor.lat,
                anchor.lon,
                poi.lat,
                poi.lon,
            )
            / self.distance_decay_m
        )

        utility = poi.utility.overall
        semantic = poi.anchor.semantic

        categories = Counter(p.category for p in selected)

        count = categories[poi.category]

        variety_bonus = 1.0 / (count + 1)

        unique_ratio = (
            len(categories)
            / max(len(selected), 1)
        )

        return (
            0.52 * utility
            + 0.23 * semantic
            + 0.15 * distance
            + 0.10 * variety_bonus * (1.0 + self.diversity_weight * unique_ratio)
        )