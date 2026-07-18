from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from .candidate import POI
from .intent import StructuredIntent

class ItineraryStop(BaseModel):
    poi: POI
    day: int
    order_in_day: int
    arrival_time: str
    departure_time: str
    travel_time_to_next_minutes: Optional[int] = None
    travel_mode: str = "walking"
    notes: str = ""

class DayPlan(BaseModel):
    day: int
    date: Optional[str] = None
    theme: str = ""
    total_walking_km: float = 0.0
    total_cost_usd: float = 0.0
    stops: list[ItineraryStop] = Field(default_factory=list)


class ItineraryScore(BaseModel):
    total: float
    preference_alignment: float
    spatial_efficiency: float
    temporal_feasibility: float
    diversity: float


class ItineraryMetadata(BaseModel):
    total_pois_retrieved: int
    clusters_found: int
    anchors_selected: int


class Itinerary(BaseModel):
    intent: StructuredIntent
    score: ItineraryScore
    metadata: ItineraryMetadata
    days: list[DayPlan]
    anchors: list[POI] = Field(default_factory=list)
