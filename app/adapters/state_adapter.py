"""
Read-only helpers over PlanningState for cross-cutting concerns
(debugging, reporting, itinerary display) that shouldn't need to know
which of the four POI-stage lists is currently populated.
"""
from __future__ import annotations
from app.schemas import PlanningState, POI


def latest_pois(state: PlanningState) -> list[POI]:
    """Most-advanced non-empty POI list, in pipeline order."""
    for pois in (state.planned_pois, state.clustered_pois, state.scored_pois, state.raw_pois):
        if pois:
            return pois
    return []


def poi_count_by_stage(state: PlanningState) -> dict[str, int]:
    return {
        "raw": len(state.raw_pois),
        "scored": len(state.scored_pois),
        "clustered": len(state.clustered_pois),
        "planned": len(state.planned_pois),
    }


def has_failed(state: PlanningState) -> bool:
    return bool(state.metadata.failed_stages)