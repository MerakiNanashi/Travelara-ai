"""
main.py — End-to-end trip planning pipeline.

  extract_intent (Gemini)
    → run_retrieval x2 (Geoapify + Foursquare) + dedup + filter
    → select_clusters (score → cluster → prune)
    → build_candidate_pool (enrich → semantic → anchor → expand)
    → [itinerary builder goes here]
"""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

from app.extractor import extract_intent
from app.providers.provider import run_retrieval
from app.clustering.cluster import select_clusters
from app.clustering.score import build_candidate_pool
from app.schemas import POI, StructuredIntent


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_name(poi: POI) -> str:
    """Return the English Wikidata label when available, else the provider name."""
    if poi.wiki_enrichment:
        en = poi.wiki_enrichment.get("en_name")
        if en and en.strip():
            return en.strip()
    return poi.name


def _print_itinerary(candidate_pool: list[dict]) -> None:
    total_pois = sum(len(day["pois"]) for day in candidate_pool)
    print(f"\n{'═' * 60}")
    print(f"  ITINERARY  —  {len(candidate_pool)} days  |  {total_pois} places")
    print(f"{'═' * 60}")

    for i, day in enumerate(candidate_pool, 1):
        anchor     = day["anchor"]
        cluster    = day["cluster"]
        pois       = day["pois"]
        score      = cluster["survival_score"]
        anchor_name = _display_name(anchor)

        print(f"\n  Day {i}  ┃  anchor: {anchor_name}  (cluster {cluster['cluster_id']}, score {score:.3f})")
        print(f"  {'─' * 56}")

        for j, poi in enumerate(pois):
            marker   = "★" if poi.id == anchor.id else " "
            name     = _display_name(poi)
            category = poi.category
            rating   = f"  ★{poi.rating:.1f}" if poi.rating else ""
            anchor_score = f"  anchor={poi.anchor_score.overall_anchor:.3f}"
            utility  = f"  utility={poi.utility_score.raw_score:.2f}" if poi.utility_score else ""

            print(f"  {marker} {j+1:>2}. {name:<36} [{category}]{rating}{anchor_score}{utility}")

            if poi.wiki_enrichment and poi.wiki_enrichment.get("description"):
                desc = poi.wiki_enrichment["description"]
                # Truncate long descriptions to one line
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                print(f"       {desc}")

    print(f"\n{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/plan", tags=["Planning"])


@router.post("/", summary="Full planning pipeline")
async def plan_trip(
    query: str,
    *,
    protected_top_n: int = 50,
    pruning_percentile: float = 60.0,
    target_per_cluster: int = 6,
    expansion_radius_m: float = 600.0,
    debug: bool = False,
) -> list[dict]:
    """
    Full pipeline from a raw user query to a per-day candidate pool.

    Returns
    -------
    list[dict]
        One entry per scheduled day: {cluster, anchor, pois}
    """

    # ── 1. Extract structured intent ──────────────────────────────────────
    if debug:
        print("\n=== STEP 1: Intent Extraction ===")

    intent: StructuredIntent = await extract_intent(query)

    if debug:
        print(f"Destination : {intent.destination}")
        print(f"Days        : {intent.days}")
        print(f"Stay        : {intent.stay_location}")
        print(f"Budget      : {intent.budget}")
        print(f"Preferences : {intent.preferences.model_dump()}")
        print(f"Constraints : {intent.constraints.model_dump()}")

    # ── 2. Retrieve POIs from both providers concurrently ─────────────────
    if debug:
        print("\n=== STEP 2: POI Retrieval ===")

    (pois_ga, _, _), (pois_fs, _, _) = await asyncio.gather(
        run_retrieval(source="GA", intent=intent, debug=debug),
        run_retrieval(source="FS", intent=intent, debug=debug),
    )

    pois = pois_ga + pois_fs

    if debug:
        print(f"\nTotal POIs (post-dedup): {len(pois)}")
        print(f"  Geoapify   : {len(pois_ga)}")
        print(f"  Foursquare : {len(pois_fs)}")

    if not pois:
        raise ValueError(
            f"No POIs retrieved for '{intent.destination}'. "
            "Check provider API keys and destination spelling."
        )

    # ── 3. Score → cluster → prune ────────────────────────────────────────
    if debug:
        print("\n=== STEP 3: Clustering & Pruning ===")

    selected_pois, selected_clusters, cluster_map = select_clusters(
        pois,
        intent,
        protected_top_n=protected_top_n,
        pruning_percentile=pruning_percentile,
    )

    if debug:
        total_clusters = len({cluster_map[p.id] for p in pois})
        enrichable = sum(
            1 for p in selected_pois
            if p.wiki_and_media and p.wiki_and_media.get("wikidata")
        )
        print(f"Total clusters      : {total_clusters}")
        print(f"Surviving clusters  : {len(selected_clusters)}")
        print(f"Pool POIs           : {len(selected_pois)}")
        print(f"  with Wikidata QID : {enrichable}")

    if not selected_clusters:
        raise ValueError(
            "No clusters survived pruning. "
            "Try lowering pruning_percentile or increasing protected_top_n."
        )

    # ── 4. Enrich → semantic → anchor → expand ────────────────────────────
    if debug:
        print("\n=== STEP 4: Enrichment + Scoring + Candidate Pool ===")

    candidate_pool = await build_candidate_pool(
        pool_pois=selected_pois,
        selected_clusters=selected_clusters,
        cluster_map=cluster_map,
        intent=intent,
        days=intent.days,
        target_per_cluster=target_per_cluster,
        expansion_radius_m=expansion_radius_m,
    )

    # ── 5. Print itinerary ────────────────────────────────────────────────
    _print_itinerary(candidate_pool)

    return candidate_pool


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    query = (
        " ".join(sys.argv[1:])
        or "5-day Tokyo trip, interested in museums and food, medium budget, staying near Shinjuku"
    )

    result = asyncio.run(plan_trip(query, debug=True))