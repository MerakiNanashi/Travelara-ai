"""
Graph service:
- Builds sparse KNN spatial graph via BallTree
- DBSCAN spatial clustering
- Node utility scoring
"""
from __future__ import annotations
import hdbscan
import math
import numpy as np

from app.clustering.filter import Filter
from app.schemas import POI, StructuredIntent

def score_all_pois(pois: list[POI], intent: StructuredIntent) -> list[POI]:
    filter_obj = Filter()
    scores = filter_obj.score_filter(pois, intent)

    score_lookup = {
        score.id: score
        for score in scores
    }

    for poi in pois:
        poi.utility_score = score_lookup.get(poi.id, 0.0)

    return sorted(
        pois,
        key=lambda p: p.utility_score.raw_score,
        reverse=True
    )

# ─── Haversine distance ───────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_m(lat1, lon1, lat2, lon2) / 1000.0


# ─── Spatial clustering ───────────────────────────────────────────────────────

def cluster_pois(
    pois: list[POI],
    min_cluster_size: int = 5,
    min_samples: int = 2
) -> dict[str, int]:

    if len(pois) < 2:
        return {p.id: 0 for p in pois}

    coords = np.radians([[p.lat, p.lon] for p in pois])

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="haversine"
    )

    labels = clusterer.fit_predict(coords)

    cluster_map = {pois[i].id: int(labels[i])
                for i in range(len(pois))}

    return _reassign_noise(pois,cluster_map)


def _reassign_noise(pois: list[POI], cluster_map: dict[str, int]) -> dict[str, int]:
    """Assign noise points to the nearest cluster."""
    poi_by_id = {p.id: p for p in pois}
    clustered = [p for p in pois if cluster_map[p.id] != -1]
    if not clustered:
        # All noise → put everything in cluster 0
        return {p.id: 0 for p in pois}

    for poi in pois:
        if cluster_map[poi.id] == -1:
            nearest = min(
                clustered,
                key=lambda c: haversine_m(poi.lat, poi.lon, c.lat, c.lon)
            )
            cluster_map[poi.id] = cluster_map[nearest.id]

    return cluster_map


def group_by_cluster(pois: list[POI], cluster_map: dict[str, int]) -> dict[int, list[POI]]:
    groups: dict[int, list[POI]] = {}
    for poi in pois:
        cid = cluster_map.get(poi.id, 0)
        groups.setdefault(cid, []).append(poi)
    return groups
