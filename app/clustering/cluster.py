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
    for poi, score in zip(pois, scores):
        poi.planning.utility = score

    return sorted(
        pois,
        key=lambda p: p.planning.utility.raw if p.planning.utility else 0.0,
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

def _shannon_diversity(members: list[POI]) -> float:
    """
    Normalized Shannon entropy of category distribution within a cluster,
    scaled to [0, 1]. 0 = single category, 1 = maximally spread across
    categories present. Used to keep mixed-category clusters competitive
    against large single-category clusters during pruning.
    """
    if len(members) <= 1:
        return 0.0

    counts: dict[str, int] = defaultdict(int)
    for p in members:
        counts[p.category] += 1

    n = len(members)
    k = len(counts)  # distinct categories present in this cluster

    if k <= 1:
        return 0.0

    entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
    max_entropy = math.log(k)  # entropy if categories were evenly distributed

    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_cluster_scores(
    pois: list[POI],
    cluster_map: dict[str, int],
    protected_top_n: int = 50,
    diversity_weight: float = 0.15,
) -> list[dict]:
    """
    Score every cluster on four quality metrics plus a category-diversity
    metric, and return ALL ranked clusters. Pruning (percentile threshold)
    is applied in select_clusters so callers that need the full ranked
    list can still get it.

    `diversity_weight` controls how much category diversity is allowed to
    rescue a mixed cluster vs. a homogeneous one of similar quality. The
    four quality terms are scaled down by (1 - diversity_weight) so the
    overall score stays on a comparable footing to before.
    """
    clusters: dict[int, list[POI]] = defaultdict(list)
    for poi in pois:
        clusters[cluster_map[poi.id]].append(poi)

    # Top-N POIs globally → their clusters are always protected
    sorted_pois = sorted(
        pois,
        key=lambda p: p.planning.utility.raw if p.planning.utility is not None else 0.0,
        reverse=True,
    )
    protected_poi_ids = {p.id for p in sorted_pois[:protected_top_n]}

    cluster_stats: dict[int, dict] = {}

    for cluster_id, members in clusters.items():
        scores = [
            p.planning.utility.raw
            for p in members
            if p.planning.utility is not None
        ] or [0.0]

        cluster_stats[cluster_id] = {
            "cluster_id": cluster_id,
            "sum_score":  float(np.sum(scores)),
            "max_score":  float(np.max(scores)),
            "p90_score":  float(np.percentile(scores, 90)),
            "size":       len(members),
            "density":    float(np.sum(scores)) / max(len(members), 1),
            "category_diversity": _shannon_diversity(members),
            "protected":  any(p.id in protected_poi_ids for p in members),
        }

    # Normalize across clusters before combining into survival score
    norm_sum     = _normalize({cid: c["sum_score"] for cid, c in cluster_stats.items()})
    norm_max     = _normalize({cid: c["max_score"] for cid, c in cluster_stats.items()})
    norm_p90     = _normalize({cid: c["p90_score"] for cid, c in cluster_stats.items()})
    norm_density = _normalize({cid: c["density"]   for cid, c in cluster_stats.items()})
    # category_diversity is already in [0, 1], no normalization needed

    quality_weight = 1.0 - diversity_weight

    for cid, c in cluster_stats.items():
        quality_component = (
            0.40 * norm_sum[cid]
            + 0.25 * norm_max[cid]
            + 0.25 * norm_p90[cid]
            + 0.10 * norm_density[cid]
        )
        c["survival_score"] = (
            quality_weight * quality_component
            + diversity_weight * c["category_diversity"]
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
    diversity_weight: float = 0.15,
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
        scored_pois, cluster_map, protected_top_n=protected_top_n,
        diversity_weight=diversity_weight,
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