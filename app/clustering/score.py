"""
Scoring service:
- SemanticScorer   – BGE-M3 embedding similarity between user intent and POIs
- Anchor scoring   – spatial representativeness, expansion potential, connectivity
- Candidate pool   – selects anchors per day and expands to fill slots
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.clustering.cluster import _normalize, haversine_m
from app.details.wikidata import enrich_selected_pois
from app.schemas import POI, StructuredIntent


# ---------------------------------------------------------------------------
# Semantic scorer (BGE-M3, singleton)
# ---------------------------------------------------------------------------

class SemanticScorer:
    _model = None

    def __init__(self, model_name: str = "BAAI/bge-m3", device=None):
        if SemanticScorer._model is None:
            SemanticScorer._model = SentenceTransformer(model_name, device=device)
        self.model = SemanticScorer._model

    @staticmethod
    def _build_user_profile(intent: StructuredIntent) -> str:
        prefs = [
            f"{pref.category} ({pref.weight:.2f})"
            for pref in intent.preferences
            if pref.weight > 0
        ]
        return f"""
Destination: {intent.destination.value}

Stay location:
{intent.stay_location.value}

Budget:
{intent.budget.value}

Trip length:
{intent.days.value} days

Walking limit:
{intent.constraints.walking_limit_km} km
    
Interested in:
{", ".join(prefs)}
""".strip()

    @staticmethod
    def _build_poi_document(poi: POI) -> str:
        wiki = ""
        if poi.wiki_enrichment:
            wiki = poi.wiki_enrichment.get("description") or ""
        tags = ", ".join(poi.tags or [])
        return f"""
Name:
{poi.name}

Category:
{poi.category}

Tags:
{tags}

Description:
{wiki}
""".strip()

    def score(self, pois: list[POI], intent: StructuredIntent) -> list[float]:
        if not pois:
            return []

        user_doc  = self._build_user_profile(intent)
        poi_docs  = [self._build_poi_document(p) for p in pois]

        user_embedding = self.model.encode(
            user_doc,
            convert_to_tensor=True,
            normalize_embeddings=True,
        )
        poi_embeddings = self.model.encode(
            poi_docs,
            convert_to_tensor=True,
            normalize_embeddings=True,
            batch_size=64,
        )

        raw = torch.matmul(poi_embeddings, user_embedding).cpu().tolist()
        return [(s + 1) / 2 for s in raw]  # [-1, 1] → [0, 1]


# ---------------------------------------------------------------------------
# Stage 1 — Semantic scoring (post-enrichment)
# ---------------------------------------------------------------------------

def _apply_semantic_scores(pois: list[POI], intent: StructuredIntent) -> None:
    """Write BGE-M3 similarity scores onto each POI in-place."""
    scorer = SemanticScorer()
    for poi, score in zip(pois, scorer.score(pois, intent)):
        poi.planning.anchor.semantic = score


# ---------------------------------------------------------------------------
# Stage 2 — Anchor scoring (post-semantic)
# ---------------------------------------------------------------------------

def _compute_anchor_scores(
    pois: list[POI],
    cluster_map: dict[str, int],
    sigma_m: float = 500.0,
    neighbor_radius_m: float = 400.0,
) -> None:
    """
    Compute spatial + utility anchor scores for every POI in the pool.
    Writes results onto each POI in-place.
    """
    clusters: dict[int, list[POI]] = defaultdict(list)
    for poi in pois:
        clusters[cluster_map[poi.id]].append(poi)

    utility = _normalize({
        p.id: p.planning.utility.raw if p.planning.utility else 0.0
        for p in pois
        if p.planning.utility is not None
    })

    for members in clusters.values():

        if len(members) == 1:
            poi = members[0]
            anchor_score = poi.planning.anchor
            anchor_score.semantic = poi.planning.utility.semantic or 0.0
            anchor_score.representative = 1.0
            anchor_score.expansion      = 1.0
            anchor_score.connectivity   = 1.0
            anchor_score.importance     = poi.popularity_score or 0.0
            anchor_score.overall = (
                0.30 * anchor_score.semantic 
                + 0.25 * utility.get(poi.id, 0.0)
                + 0.20 * anchor_score.representative
                + 0.15 * anchor_score.expansion
                + 0.05 * anchor_score.connectivity
                + 0.05 * anchor_score.importance
            )
            continue

        centroid_lat = np.mean([p.lat for p in members])
        centroid_lon = np.mean([p.lon for p in members])
        max_centroid_dist = max(
            haversine_m(centroid_lat, centroid_lon, p.lat, p.lon)
            for p in members
        ) + 1e-6

        represent:    dict[str, float] = {}
        expansion:    dict[str, float] = {}
        connectivity: dict[str, int]   = {}
        importance:   dict[str, float] = {}

        for poi in members:
            represent[poi.id] = 1.0 - (
                haversine_m(centroid_lat, centroid_lon, poi.lat, poi.lon)
                / max_centroid_dist
            )

            exp_score  = 0.0
            conn_score = 0

            for other in members:
                if other.id == poi.id:
                    continue
                d = haversine_m(poi.lat, poi.lon, other.lat, other.lon)
                u = utility.get(other.id, 0.0)
                exp_score += u * math.exp(-d / sigma_m)
                if d <= neighbor_radius_m and u >= 0.6:
                    conn_score += 1

            expansion[poi.id]    = exp_score
            connectivity[poi.id] = conn_score
            importance[poi.id]   = poi.popularity_score or 0.0

        represent    = _normalize(represent)
        expansion    = _normalize(expansion)
        connectivity = _normalize(connectivity)
        importance   = _normalize(importance)

        for poi in members:
            u = utility.get(poi.id, 0.0)
            anchor_score = poi.planning.anchor
            anchor_score.representative = represent[poi.id]
            anchor_score.expansion      = expansion[poi.id]
            anchor_score.connectivity   = connectivity[poi.id]
            anchor_score.importance     = importance[poi.id]
            anchor_score.overall = (
                0.30 * anchor_score.semantic
                + 0.25 * u
                + 0.20 * represent[poi.id]
                + 0.15 * expansion[poi.id]
                + 0.05 * connectivity[poi.id]
                + 0.05 * importance[poi.id]
            )


# ---------------------------------------------------------------------------
# Stage 3 — Candidate scoring + expansion
# ---------------------------------------------------------------------------

def _candidate_score(
    anchor: POI,
    poi: POI,
    selected: list[POI] | None = None,
    diversity_penalty_weight: float = 0.12,
) -> float:
    """
    Quality + proximity-to-anchor score, with an optional category-diversity
    penalty. `selected` is the set of POIs already picked for this day so
    far — each prior pick of the same category nudges this poi's score
    down, so a homogeneous cluster (e.g. 8 great restaurants) doesn't
    crowd out a smaller number of equally-good but different categories.

    Pass `selected=None` (or omit it) to get the old quality/proximity-only
    behavior, e.g. for one-off comparisons outside the greedy fill loops.
    """
    distance_score = math.exp(
        -haversine_m(anchor.lat, anchor.lon, poi.lat, poi.lon) / 500.0
    )
    base = (
        0.60 * (poi.planning.utility.overall if poi.planning.utility else 0.0)
        + 0.25 * poi.planning.anchor.semantic
        + 0.15 * distance_score
    )

    if not selected:
        return base

    same_category_count = sum(1 for s in selected if s.category == poi.category)
    diversity_penalty = diversity_penalty_weight * same_category_count

    return base - diversity_penalty


# ---------------------------------------------------------------------------
# Greedy diversity-aware fill
# ---------------------------------------------------------------------------

def _greedy_fill(
    anchor: POI,
    candidates: list[POI],
    selected: list[POI],
    used: set[str],
    quota: int,
) -> None:
    """
    Greedily pick from `candidates` until `selected` reaches `quota`,
    re-scoring after every pick so the diversity penalty in
    _candidate_score reflects categories already chosen. Mutates
    `selected` and `used` in place.

    A single `sorted(..., key=_candidate_score)` pass can't do this: the
    penalty for a category depends on how many of that category are
    already in `selected`, which changes after every pick.
    """
    remaining = [p for p in candidates if p.id not in used]

    while remaining and len(selected) < quota:
        best = max(remaining, key=lambda p: _candidate_score(anchor, p, selected))
        selected.append(best)
        used.add(best.id)
        remaining.remove(best)


def _expand_around_anchors(
    selected_clusters: list[dict],
    pool_pois: list[POI],
    cluster_map: dict[str, int],
    days: int,
    target_per_cluster: int = 6,
    expansion_radius_m: float = 600.0,
) -> list[dict]:
    """
    For each of the top `days` clusters (by survival_score):
      1. Pick the POI with highest overall_anchor as the day anchor.
      2. Fill the slot from same-cluster POIs, greedily re-ranked each
         pick by quality/proximity minus a category-diversity penalty.
      3. If still under quota, pull in nearby POIs from other clusters
         under the same diversity-aware greedy fill.

    Returns list of: {cluster, anchor, pois}
    """
    by_cluster: dict[int, list[POI]] = defaultdict(list)
    for poi in pool_pois:
        by_cluster[cluster_map[poi.id]].append(poi)

    scheduled = sorted(
        selected_clusters,
        key=lambda c: c["survival_score"],
        reverse=True,
    )[:days]

    used: set[str] = set()
    final_days: list[dict] = []

    for cluster in scheduled:
        cid     = cluster["cluster_id"]
        members = by_cluster.get(cid, [])

        if not members:
            continue

        members.sort(key=lambda p: p.anchor_score.overall_anchor, reverse=True)
        anchor = members[0]
        used.add(anchor.id)
        candidates = [anchor]

        # Fill from within cluster — diversity-aware greedy
        _greedy_fill(
            anchor=anchor,
            candidates=members[1:],
            selected=candidates,
            used=used,
            quota=target_per_cluster,
        )

        # Expand cross-cluster if under quota — same diversity-aware greedy
        if len(candidates) < target_per_cluster:
            nearby = [
                p for p in pool_pois
                if p.id not in used
                and cluster_map[p.id] != cid
                and haversine_m(anchor.lat, anchor.lon, p.lat, p.lon) <= expansion_radius_m
            ]
            _greedy_fill(
                anchor=anchor,
                candidates=nearby,
                selected=candidates,
                used=used,
                quota=target_per_cluster,
            )

        final_days.append({
            "cluster": cluster,
            "anchor":  anchor,
            "pois":    candidates,
        })

    return final_days


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def build_candidate_pool(
    pool_pois: list[POI],
    selected_clusters: list[dict],
    cluster_map: dict[str, int],
    intent: StructuredIntent,
    days: int,
    target_per_cluster: int = 6,
    expansion_radius_m: float = 600.0,
) -> list[dict]:
    """
    Runs stages 1–3 on an already-pruned POI pool:

      Enrich (wikidata, QID-bearing POIs only)
        → Semantic Score
        → Anchor Score
        → Select Anchors + Expand
        → Final Candidate Pool

    `pool_pois` and `selected_clusters` come from cluster.select_clusters().
    """
    # Enrich only POIs that carry a Wikidata QID
    enrichable = [
        p for p in pool_pois
        if p.wiki_and_media and p.wiki_and_media.get("wikidata")
    ]
    await enrich_selected_pois(enrichable)

    # Semantic scoring uses enriched wiki descriptions
    _apply_semantic_scores(pool_pois, intent)

    # Anchor scoring uses semantic scores + utility scores
    _compute_anchor_scores(pool_pois, cluster_map)

    # Select top `days` anchors and build per-day candidate lists
    return _expand_around_anchors(
        selected_clusters=selected_clusters,
        pool_pois=pool_pois,
        cluster_map=cluster_map,
        days=days,
        target_per_cluster=target_per_cluster,
        expansion_radius_m=expansion_radius_m,
    )