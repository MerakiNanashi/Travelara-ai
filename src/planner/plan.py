from __future__ import annotations
from datetime import datetime, timedelta

from src.shared.schemas import (
    StructuredIntent, 
    Itinerary,
    DayPlan,
    ItineraryStop,
    ItineraryScore,
    ItineraryMetadata,
    CandidateSelectionResult
)

def candidate_pool_to_itinerary(
    candidate_pool: list[CandidateSelectionResult],
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

        anchor = cluster.anchor
        pois = cluster.pois
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
                if previous.distance_m and poi.distance_m:
                    travel = max(
                        5,
                        int(abs(poi.distance_m - previous.distance_m) / 80)
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

            if poi.anchor:
                total_anchor += poi.anchor.overall

            if poi.utility:
                total_utility += poi.utility.overall

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