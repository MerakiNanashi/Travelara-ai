"""
Planner service:
1. Anchor selection (MMR-style greedy)
2. Cluster-aware day assignment
3. Local neighborhood beam search
4. Iterative refinement
5. Itinerary assembly
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta
from app.schemas import (
    POI, StructuredIntent, Itinerary, DayPlan, ItineraryStop, ItineraryScore
)
from app.clustering.cluster import (
    haversine_km, cluster_pois, group_by_cluster, score_all_pois
)
from app.config import settings


# ─── Anchor selection ─────────────────────────────────────────────────────────

def _anchor_utility(poi: POI, selected: list[POI], intent: StructuredIntent) -> float:
    """
    A_i = αP + βR + γD - δO
    D = diversity bonus (distance from already-selected anchors)
    O = overlap penalty
    """
    prefs = intent.preferences.model_dump()
    P = prefs.get(poi.category, 0.3)
    R = poi.popularity_score
    
    if not selected:
        D = 1.0
    else:
        min_dist = min(haversine_km(poi.lat, poi.lon, s.lat, s.lon) for s in selected)
        D = min(min_dist / 5.0, 1.0)  # normalize: 5km+ = max diversity

    # Overlap penalty: penalise if same category already well covered
    same_cat_count = sum(1 for s in selected if s.category == poi.category)
    O = same_cat_count * 0.1

    return 0.35 * P + 0.25 * R + 0.30 * D - 0.10 * O


def select_anchors(pois: list[POI], intent: StructuredIntent, max_anchors: int = 6) -> list[POI]:
    """Greedy MMR-style anchor selection."""
    candidates = [p for p in pois if p.utility_score > 0.3]
    if not candidates:
        candidates = pois[:20]

    # Always include must-visit POIs first
    must_names = {m.lower() for m in intent.constraints.must_visit}
    must_pois = [p for p in candidates if any(m in p.name.lower() for m in must_names)]
    selected = must_pois[:]

    remaining = [p for p in candidates if p not in selected]

    while len(selected) < max_anchors and remaining:
        best_score = -math.inf
        best_poi = None
        for poi in remaining:
            score = _anchor_utility(poi, selected, intent)
            if score > best_score:
                best_score = score
                best_poi = poi
        if best_poi:
            best_poi.is_anchor = True
            selected.append(best_poi)
            remaining.remove(best_poi)

    for p in selected:
        p.is_anchor = True

    return selected


# ─── Neighborhood expansion ───────────────────────────────────────────────────

def expand_neighborhood(anchor: POI, all_pois: list[POI], radius_km: float = 2.0) -> list[POI]:
    """Return POIs within radius_km of anchor, excluding anchor itself."""
    return [
        p for p in all_pois
        if p.id != anchor.id and haversine_km(anchor.lat, anchor.lon, p.lat, p.lon) <= radius_km
    ]


# ─── Beam search for day sequencing ──────────────────────────────────────────

def _edge_cost(a: POI, b: POI) -> float:
    """Lower = better transition. Combines distance + category compatibility."""
    dist_km = haversine_km(a.lat, a.lon, b.lat, b.lon)
    dist_penalty = min(dist_km / 3.0, 1.0)  # 3km+ = max penalty

    # Category compatibility bonus
    compatibility = {
        ("museums", "food"): 0.2,
        ("history", "food"): 0.2,
        ("arts", "food"): 0.2,
        ("nature", "food"): 0.15,
        ("museums", "arts"): 0.15,
        ("history", "museums"): 0.15,
        ("shopping", "food"): 0.1,
        ("nightlife", "food"): 0.1,
    }
    compat_bonus = compatibility.get((a.category, b.category), 0.0)
    compat_bonus += compatibility.get((b.category, a.category), 0.0)

    return dist_penalty - compat_bonus


def beam_search_sequence(
    candidates: list[POI],
    max_stops: int = 5,
    beam_width: int = 3,
) -> list[POI]:
    """
    Beam search to find optimal daily sequence.
    Returns ordered list of POIs for a single day.
    Complexity: O(B * L * D) where B=beam, L=local candidates, D=depth
    """
    if not candidates:
        return []
    if len(candidates) <= max_stops:
        return candidates

    # Sort by utility to seed beams
    sorted_cands = sorted(candidates, key=lambda p: p.utility_score, reverse=True)

    # Initialize beams: each beam is (sequence, cumulative_score)
    beams: list[tuple[list[POI], float]] = [
        ([p], p.utility_score) for p in sorted_cands[:beam_width]
    ]

    for _ in range(max_stops - 1):
        new_beams: list[tuple[list[POI], float]] = []
        for seq, score in beams:
            visited_ids = {p.id for p in seq}
            last = seq[-1]
            expansions = [p for p in candidates if p.id not in visited_ids]
            if not expansions:
                new_beams.append((seq, score))
                continue
            for cand in expansions:
                edge = _edge_cost(last, cand)
                new_score = score + cand.utility_score - edge
                new_beams.append((seq + [cand], new_score))

        # Keep top beam_width beams
        new_beams.sort(key=lambda x: x[1], reverse=True)
        beams = new_beams[:beam_width]

    best_seq, _ = beams[0]
    return best_seq[:max_stops]


# ─── Time assignment ──────────────────────────────────────────────────────────

_DAY_START_HOUR = 9  # 09:00


def assign_times(stops: list[POI]) -> list[tuple[str, str, int]]:
    """
    Returns list of (arrival_time, departure_time, travel_to_next_minutes).
    Assumes walking speed of 5 km/h.
    """
    results = []
    current_minutes = _DAY_START_HOUR * 60

    for i, poi in enumerate(stops):
        arrival = _fmt_time(current_minutes)
        duration = poi.avg_duration_minutes
        departure_minutes = current_minutes + duration
        departure = _fmt_time(departure_minutes)

        # Travel to next stop
        if i + 1 < len(stops):
            dist_km = haversine_km(poi.lat, poi.lon, stops[i + 1].lat, stops[i + 1].lon)
            travel_min = int((dist_km / 5.0) * 60)  # walking 5 km/h
            travel_min = max(travel_min, 5)
            current_minutes = departure_minutes + travel_min
        else:
            travel_min = 0

        results.append((arrival, departure, travel_min))

    return results


def _fmt_time(minutes: int) -> str:
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


# ─── Itinerary evaluation ─────────────────────────────────────────────────────

def evaluate_itinerary(days: list[DayPlan], intent: StructuredIntent) -> ItineraryScore:
    prefs = intent.preferences.model_dump()
    all_stops = [s for d in days for s in d.stops]

    if not all_stops:
        return ItineraryScore(total=0, preference_alignment=0, spatial_efficiency=0, temporal_feasibility=1, diversity=0)

    # Preference alignment
    pref_scores = [prefs.get(s.poi.category, 0.3) for s in all_stops]
    pref_align = sum(pref_scores) / len(pref_scores)

    # Spatial efficiency: avg walking per day (lower = better, max 1.0)
    avg_walk = sum(d.total_walking_km for d in days) / len(days)
    spatial_eff = max(0, 1.0 - avg_walk / intent.constraints.walking_limit_km)

    # Temporal feasibility (placeholder)
    temporal = 1.0

    # Diversity: unique categories / total stops
    unique_cats = len({s.poi.category for s in all_stops})
    diversity = min(unique_cats / 5.0, 1.0)

    total = 0.35 * pref_align + 0.30 * spatial_eff + 0.15 * temporal + 0.20 * diversity

    return ItineraryScore(
        total=round(total, 3),
        preference_alignment=round(pref_align, 3),
        spatial_efficiency=round(spatial_eff, 3),
        temporal_feasibility=round(temporal, 3),
        diversity=round(diversity, 3),
    )


# ─── Iterative refinement ─────────────────────────────────────────────────────

def refine_day(day: DayPlan, all_pois: list[POI], intent: StructuredIntent) -> DayPlan:
    """
    Single refinement pass:
    - Remove stops that create excessive backtracking
    - Add better POI if available nearby
    """
    if len(day.stops) < 2:
        return day

    # Detect backtracking: if stop[i+2] is closer to stop[i] than stop[i+1]
    stops_pois = [s.poi for s in day.stops]
    refined = [stops_pois[0]]

    for i in range(1, len(stops_pois)):
        prev = refined[-1]
        curr = stops_pois[i]
        dist = haversine_km(prev.lat, prev.lon, curr.lat, curr.lon)
        # Only add if within walking limit contribution
        if dist <= intent.constraints.walking_limit_km / len(stops_pois):
            refined.append(curr)
        else:
            # Try to find a better local substitute
            nearby = [
                p for p in all_pois
                if p.id not in {r.id for r in refined}
                and haversine_km(prev.lat, prev.lon, p.lat, p.lon) < dist * 0.7
            ]
            if nearby:
                best = max(nearby, key=lambda p: p.utility_score)
                refined.append(best)
            else:
                refined.append(curr)

    return _build_day_plan(day.day, day.date, refined, day.cluster_id)


def _build_day_plan(
    day_num: int,
    date: str | None,
    pois: list[POI],
    cluster_id: int | None = None,
) -> DayPlan:
    times = assign_times(pois)
    total_walk = 0.0
    total_cost = 0.0
    stops = []

    for i, (poi, (arr, dep, travel)) in enumerate(zip(pois, times)):
        if i + 1 < len(pois):
            total_walk += haversine_km(poi.lat, poi.lon, pois[i + 1].lat, pois[i + 1].lon)
        total_cost += poi.estimated_cost_usd

        stops.append(ItineraryStop(
            poi=poi,
            day=day_num,
            order_in_day=i + 1,
            arrival_time=arr,
            departure_time=dep,
            travel_time_to_next_minutes=travel if i + 1 < len(pois) else None,
            travel_mode="walking",
            notes="",
        ))

    # Generate day theme from dominant category
    if pois:
        cats = [p.category for p in pois]
        dominant = max(set(cats), key=cats.count)
        theme = f"{dominant.title()} & exploration"
    else:
        theme = "Exploration day"

    return DayPlan(
        day=day_num,
        date=date,
        theme=theme,
        stops=stops,
        total_walking_km=round(total_walk, 2),
        total_cost_usd=round(total_cost, 2),
        cluster_id=cluster_id,
    )


# ─── Master planner ───────────────────────────────────────────────────────────

def build_itinerary(
    pois: list[POI],
    intent: StructuredIntent,
) -> Itinerary:
    """
    Full planning pipeline:
    retrieval → score → cluster → anchor select → local optimize → refine → assemble
    """
    # 1. Score all POIs
    pois = score_all_pois(pois, intent)

    # 2. Cluster
    cluster_map = cluster_pois(pois, eps_km=1.2, min_samples=2)
    cluster_groups = group_by_cluster(pois, cluster_map)

    # 3. Select anchors
    anchors = select_anchors(pois, intent, max_anchors=settings.max_anchors)

    # 4. Assign anchors to days (one or two anchors per day)
    days_count = intent.days
    stops_per_day = max(3, min(6, 20 // days_count))  # 3-6 stops/day
    anchor_days = _assign_anchors_to_days(anchors, days_count)

    # 5. Build each day
    day_plans: list[DayPlan] = []
    used_ids: set[str] = set()

    start_date = None
    if intent.start_date:
        try:
            start_date = datetime.strptime(intent.start_date, "%Y-%m-%d")
        except ValueError:
            pass

    for day_num in range(1, days_count + 1):
        day_anchors = anchor_days.get(day_num, [])
        if not day_anchors and pois:
            day_anchors = [max(
                [p for p in pois if p.id not in used_ids],
                key=lambda p: p.utility_score,
                default=pois[0],
            )]

        # Expand neighborhood around day's anchors
        local_candidates: list[POI] = list({p.id: p for anchor in day_anchors
                                             for p in expand_neighborhood(anchor, pois, settings.anchor_radius_km)
                                             if p.id not in used_ids}.values())

        # Add anchors themselves
        for a in day_anchors:
            if a not in local_candidates:
                local_candidates.insert(0, a)

        if not local_candidates:
            local_candidates = [p for p in pois if p.id not in used_ids][:stops_per_day]

        # Beam search for optimal sequence
        sequence = beam_search_sequence(
            local_candidates,
            max_stops=stops_per_day,
            beam_width=settings.beam_width,
        )

        used_ids.update(p.id for p in sequence)

        date_str = None
        if start_date:
            date_str = (start_date + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")

        # Cluster id of first anchor
        cluster_id = cluster_map.get(day_anchors[0].id) if day_anchors else None
        day_plan = _build_day_plan(day_num, date_str, sequence, cluster_id)
        day_plans.append(day_plan)

    # 6. Iterative refinement
    for _ in range(settings.refinement_iterations):
        day_plans = [refine_day(d, pois, intent) for d in day_plans]

    # 7. Evaluate
    score = evaluate_itinerary(day_plans, intent)

    return Itinerary(
        intent=intent,
        days=day_plans,
        score=score,
        anchors=anchors,
        metadata={
            "total_pois_retrieved": len(pois),
            "clusters_found": len(cluster_groups),
            "anchors_selected": len(anchors),
        },
    )


def _assign_anchors_to_days(anchors: list[POI], days: int) -> dict[int, list[POI]]:
    """Distribute anchors across days roughly evenly."""
    assignment: dict[int, list[POI]] = {d: [] for d in range(1, days + 1)}
    for i, anchor in enumerate(anchors):
        day = (i % days) + 1
        assignment[day].append(anchor)
    return assignment
