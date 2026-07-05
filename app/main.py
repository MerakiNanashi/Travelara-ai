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
from datetime import datetime, timedelta

from app.extractor import extract_intent
from app.providers.provider import run_retrieval
from app.clustering.cluster import select_clusters
from app.clustering.score import build_candidate_pool
from app.schemas import (
    POI, 
    StructuredIntent, 
    PlanningRequest,
    PlanResponse,
    Itinerary,
    DayPlan,
    ItineraryStop,
    ItineraryScore,
    ItineraryMetadata,
    ExtractionResult
)

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
            anchor_score = f"  anchor={poi.planning.utility.overall:.3f}"
            utility  = f"  utility={poi.planning.utility.raw:.2f}" if poi.planning.utility.raw is not None else ""

            print(f"  {marker} {j+1:>2}. {name:<36} [{category}]{rating}{anchor_score}{utility}")

            if poi.wiki_enrichment and poi.wiki_enrichment.get("description"):
                desc = poi.wiki_enrichment["description"]
                # Truncate long descriptions to one line
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                print(f"       {desc}")

    print(f"\n{'═' * 60}\n")


def candidate_pool_to_itinerary(
    candidate_pool: list[dict],
    intent: StructuredIntent,
) -> Itinerary:

    days = []
    anchors = []

    total_anchor = 0
    total_utility = 0
    total_pois = 0

    start = None
    if intent.start_date.value:
        start = datetime.fromisoformat(intent.start_date.value)

    for day_num, cluster in enumerate(candidate_pool, start=1):

        anchor = cluster["anchor"]
        pois = cluster["pois"]

        anchors.append(anchor)

        current = datetime.strptime("09:00", "%H:%M")

        walking = 0.0
        cost = 0.0

        stops = []

        previous = None

        for order, poi in enumerate(pois, start=1):

            duration = timedelta(minutes=90)

            arrival = current
            departure = arrival + duration

            if previous is None:
                travel = None
            else:
                if previous.distance and poi.distance:
                    travel = max(
                        5,
                        int(abs(poi.distance - previous.distance) / 80)
                    )
                else:
                    travel = 12

                current += timedelta(minutes=travel)

                arrival = current
                departure = arrival + duration

                walking += (travel / 15.0) * 0.8

            stops.append(
                ItineraryStop(
                    poi=poi,
                    day=day_num,
                    order_in_day=order,
                    arrival_time=arrival.strftime("%H:%M"),
                    departure_time=departure.strftime("%H:%M"),
                    travel_time_to_next_minutes=travel,
                    travel_mode="walking",
                )
            )

            current = departure

            previous = poi

            total_pois += 1

            if poi.planning.anchor:
                total_anchor += poi.planning.anchor.overall

            if poi.planning.utility:
                total_utility += poi.planning.utility.overall

        if start:
            day_date = (
                start + timedelta(days=day_num - 1)
            ).date().isoformat()
        else:
            day_date = None

        theme = (
            anchor.category.replace("_", " ").title()
            + " & exploration"
        )

        days.append(
            DayPlan(
                day=day_num,
                date=day_date,
                theme=theme,
                total_walking_km=round(walking, 1),
                total_cost_usd=round(cost, 1),
                stops=stops,
            )
        )

    n = max(total_pois, 1)

    score = ItineraryScore(
        total=round(total_utility / n, 3),
        preference_alignment=round(total_anchor / n, 3),
        spatial_efficiency=0.82,
        temporal_feasibility=1.0,
        diversity=0.75,
    )

    metadata = ItineraryMetadata(
        total_pois_retrieved=total_pois,
        clusters_found=len(candidate_pool),
        anchors_selected=len(anchors),
    )

    return Itinerary(
        intent=intent,
        score=score,
        metadata=metadata,
        days=days,
        anchors=anchors,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/plan", tags=["Planning"])


@router.post("/", summary="Full planning pipeline")
async def plan_trip(
    query: PlanningRequest,
    *,
    protected_top_n: int = 50,
    pruning_percentile: float = 60.0,
    target_per_cluster: int = 6,
    expansion_radius_m: float = 600.0,
    debug: bool = True,
) -> PlanResponse:
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

    result: ExtractionResult = await extract_intent(query)
    intent: StructuredIntent = result.intent
    if debug:
        print(f"Destination : {intent.destination.value}")
        print(f"Days        : {intent.days.value}")
        print(f"Stay        : {intent.stay_location.value}")
        print(f"Budget      : {intent.budget.value}")
        print(f"Preferences : {[p.model_dump() for p in intent.preferences]}")
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
            f"No POIs retrieved for '{intent.destination.value}'. "
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
        days=intent.days.value or 1,
        target_per_cluster=target_per_cluster,
        expansion_radius_m=expansion_radius_m,
    )

    # ── 5. Print itinerary ────────────────────────────────────────────────
    _print_itinerary(candidate_pool)

    itinerary = candidate_pool_to_itinerary(candidate_pool, intent)

    return PlanResponse(success=True, itinerary=itinerary)


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