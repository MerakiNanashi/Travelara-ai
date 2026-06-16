"""
Graph service:
- Builds sparse KNN spatial graph via BallTree
- DBSCAN spatial clustering
- Node utility scoring
"""
from __future__ import annotations
import math
import numpy as np
from sklearn.neighbors import BallTree
from sklearn.cluster import DBSCAN
from app.schemas import POI, StructuredIntent
from app.config import settings


# ─── Utility scoring ──────────────────────────────────────────────────────────

def score_poi_utility(poi: POI, intent: StructuredIntent) -> float:
    """
    Node utility: W_n = αP + βR + γT + δC - εD
    P = preference relevance
    R = popularity / rating
    T = temporal suitability (placeholder; 1.0 unless constrained)
    C = category diversity bonus
    D = traversal penalty (applied later per-edge)
    """
    prefs = intent.preferences.model_dump()
    P = prefs.get(poi.category, 0.3)

    # Normalize rating 0-5 → 0-1
    R = (poi.rating / 5.0) * 0.5 + poi.popularity_score * 0.5

    T = 1.0  # temporal suitability (full opening-hours check is future work)

    C = 0.6  # contextual compatibility baseline

    alpha, beta, gamma, delta = 0.4, 0.3, 0.1, 0.2
    score = alpha * P + beta * R + gamma * T + delta * C
    return round(score, 4)


def score_all_pois(pois: list[POI], intent: StructuredIntent) -> list[POI]:
    """Score and return POIs sorted by utility descending."""
    for poi in pois:
        poi.utility_score = score_poi_utility(poi, intent)
    return sorted(pois, key=lambda p: p.utility_score, reverse=True)


# ─── KNN graph ────────────────────────────────────────────────────────────────

def build_knn_graph(pois: list[POI], k: int = 10) -> dict[str, list[str]]:
    """
    Build sparse KNN graph using BallTree (Haversine metric).
    Returns adjacency: {poi_id: [neighbor_id, ...]}
    Complexity: O(N log N)
    """
    if len(pois) < 2:
        return {p.id: [] for p in pois}

    coords = np.radians([[p.lat, p.lon] for p in pois])
    id_list = [p.id for p in pois]

    tree = BallTree(coords, metric="haversine")
    actual_k = min(k + 1, len(pois))  # +1 because query includes self
    distances, indices = tree.query(coords, k=actual_k)

    graph: dict[str, list[str]] = {}
    for i, poi in enumerate(pois):
        neighbors = [id_list[j] for j in indices[i] if id_list[j] != poi.id]
        graph[poi.id] = neighbors[:k]

    return graph


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

def cluster_pois(pois: list[POI], eps_km: float = 1.0, min_samples: int = 2) -> dict[str, int]:
    """
    DBSCAN clustering on lat/lon.
    Returns {poi_id: cluster_id}  (-1 = noise/singleton)
    """
    if len(pois) < 2:
        return {p.id: 0 for p in pois}

    coords = np.radians([[p.lat, p.lon] for p in pois])
    eps_rad = eps_km / 6371.0  # convert km to radians

    labels = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        algorithm="ball_tree",
        metric="haversine",
    ).fit_predict(coords)

    # Reassign noise points (-1) to nearest cluster
    cluster_map = {pois[i].id: int(labels[i]) for i in range(len(pois))}
    return _reassign_noise(pois, cluster_map)


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
