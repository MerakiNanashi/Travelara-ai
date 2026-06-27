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
from app.schemas import POI, StructuredIntent


# ---------------------------------------------------------------------------
# POI utility scoring
# ---------------------------------------------------------------------------

def score_all_pois(pois: list[POI], intent: StructuredIntent) -> list[POI]:
    """Run Filter scoring on all POIs and attach QualityScore to each."""
    filter_obj = Filter()
    scores = filter_obj.score_filter(pois, intent)

    score_lookup = {score.id: score for score in scores}

    for poi in pois:
        poi.utility_score = score_lookup.get(poi.id)

    return sorted(
        pois,
        key=lambda p: p.utility_score.raw_score if p.utility_score else 0.0,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Haversine distance utilities
# ---------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_m(lat1, lon1, lat2, lon2) / 1000.0


# ---------------------------------------------------------------------------
# Spatial clustering
# ---------------------------------------------------------------------------

def cluster_pois(
    pois: list[POI],
    min_cluster_size: int = 5,
    min_samples: int = 2,
) -> dict[str, int]:
    """Return a mapping of poi.id → cluster_id using HDBSCAN."""
    if len(pois) < 2:
        return {p.id: 0 for p in pois}

    coords = np.radians([[p.lat, p.lon] for p in pois])

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="haversine",
    )
    labels = clusterer.fit_predict(coords)

    cluster_map = {pois[i].id: int(labels[i]) for i in range(len(pois))}
    return _reassign_noise(pois, cluster_map)


def _reassign_noise(
    pois: list[POI],
    cluster_map: dict[str, int],
) -> dict[str, int]:
    """Assign HDBSCAN noise points (label -1) to their nearest cluster."""
    clustered = [p for p in pois if cluster_map[p.id] != -1]

    if not clustered:
        return {p.id: 0 for p in pois}

    for poi in pois:
        if cluster_map[poi.id] == -1:
            nearest = min(
                clustered,
                key=lambda c: haversine_m(poi.lat, poi.lon, c.lat, c.lon),
            )
            cluster_map[poi.id] = cluster_map[nearest.id]

    return cluster_map


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------

def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict of floats to [0, 1]."""
    if not values:
        return {}
    vmin = min(values.values())
    vmax = max(values.values())
    if vmax == vmin:
        return {k: 1.0 for k in values}
    return {k: (v - vmin) / (vmax - vmin) for k, v in values.items()}


# ---------------------------------------------------------------------------
# Cluster scoring and percentile pruning
# ---------------------------------------------------------------------------

def compute_cluster_scores(
    pois: list[POI],
    cluster_map: dict[str, int],
    protected_top_n: int = 50,
) -> list[dict]:
    """
    Score every cluster on four metrics and return ALL ranked clusters.
    Pruning (percentile threshold) is applied in select_clusters so callers
    that need the full ranked list can still get it.
    """
    clusters: dict[int, list[POI]] = defaultdict(list)
    for poi in pois:
        clusters[cluster_map[poi.id]].append(poi)

    # Top-N POIs globally → their clusters are always protected
    sorted_pois = sorted(
        pois,
        key=lambda p: p.utility_score.raw_score if p.utility_score is not None else 0.0,
        reverse=True,
    )
    protected_poi_ids = {p.id for p in sorted_pois[:protected_top_n]}

    cluster_stats: dict[int, dict] = {}

    for cluster_id, members in clusters.items():
        scores = [
            p.utility_score.raw_score
            for p in members
            if p.utility_score is not None
        ] or [0.0]

        cluster_stats[cluster_id] = {
            "cluster_id": cluster_id,
            "sum_score":  float(np.sum(scores)),
            "max_score":  float(np.max(scores)),
            "p90_score":  float(np.percentile(scores, 90)),
            "size":       len(members),
            "density":    float(np.sum(scores)) / max(len(members), 1),
            "protected":  any(p.id in protected_poi_ids for p in members),
        }

    # Normalize across clusters before combining into survival score
    norm_sum     = _normalize({cid: c["sum_score"] for cid, c in cluster_stats.items()})
    norm_max     = _normalize({cid: c["max_score"] for cid, c in cluster_stats.items()})
    norm_p90     = _normalize({cid: c["p90_score"] for cid, c in cluster_stats.items()})
    norm_density = _normalize({cid: c["density"]   for cid, c in cluster_stats.items()})

    for cid, c in cluster_stats.items():
        c["survival_score"] = (
            0.40 * norm_sum[cid]
            + 0.25 * norm_max[cid]
            + 0.25 * norm_p90[cid]
            + 0.10 * norm_density[cid]
        )

    return sorted(
        cluster_stats.values(),
        key=lambda c: c["survival_score"],
        reverse=True,
    )


def select_clusters(
    pois: list[POI],
    intent: StructuredIntent,
    protected_top_n: int = 50,
    pruning_percentile: float = 60.0,
) -> tuple[list[POI], list[dict], dict[str, int]]:
    """
    Full cluster selection pipeline:
      score_all_pois → cluster_pois → compute_cluster_scores → percentile prune

    Returns:
        selected_pois   – POIs belonging to surviving clusters (with wiki_and_media)
        selected_clusters – cluster dicts that survived pruning
        cluster_map     – full poi.id → cluster_id mapping
    """
    scored_pois = score_all_pois(pois, intent)
    cluster_map = cluster_pois(scored_pois)

    ranked_clusters = compute_cluster_scores(
        scored_pois, cluster_map, protected_top_n=protected_top_n
    )

    survival_scores = [c["survival_score"] for c in ranked_clusters]
    threshold = np.percentile(survival_scores, pruning_percentile)

    selected_clusters = [
        c for c in ranked_clusters
        if c["protected"] or c["survival_score"] >= threshold
    ]

    selected_cids = {c["cluster_id"] for c in selected_clusters}

    # Keep POIs in surviving clusters; require wiki_and_media for enrichment
    selected_pois = [
        poi for poi in scored_pois
        if cluster_map[poi.id] in selected_cids
        and poi.wiki_and_media
    ]

    return selected_pois, selected_clusters, cluster_map