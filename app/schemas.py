from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


# ─── Input / Planning Request ─────────────────────────────────────────────────

class PlanningRequest(BaseModel):
    """Raw natural-language trip request from the user."""
    query: str = Field(..., description="Natural language trip description")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "5-day Tokyo trip, interested in museums and food, moderate budget, staying near Shinjuku, avoid excessive walking"
            }
        }


# ─── Structured Intent (Extractor output) ─────────────────────────────────────

class Preferences(BaseModel):
    museums: float = 0.5
    food: float = 0.5
    nightlife: float = 0.3
    nature: float = 0.4
    shopping: float = 0.3
    arts: float = 0.4
    history: float = 0.5
    wellness: float = 0.3


class Constraints(BaseModel):
    walking_limit_km: float = 10.0
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    budget_per_day_usd: Optional[float] = None


class StructuredIntent(BaseModel):
    destination: str
    days: int
    stay_location: str
    is_international: bool
    budget: str  # low / medium / high
    preferences: Preferences
    constraints: Constraints
    start_date: Optional[str] = None


# ─── POI ──────────────────────────────────────────────────────────────────────

class POI(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    category: str
    tags: list[str] = Field(default_factory=list)
    popularity_score: float = 0.5
    opening_hours: dict = Field(default_factory=dict)
    avg_duration_minutes: int = 60
    estimated_cost_usd: float = 0.0
    rating: float = 3.0
    address: str = ""
    source: str = "foursquare"

    # Scoring fields (populated during planning)
    utility_score: float = 0.0
    is_anchor: bool = False


# ─── Itinerary ────────────────────────────────────────────────────────────────

class ItineraryStop(BaseModel):
    poi: POI
    day: int
    order_in_day: int
    arrival_time: str  # HH:MM
    departure_time: str  # HH:MM
    travel_time_to_next_minutes: Optional[int] = None
    travel_mode: str = "walking"
    notes: str = ""


class DayPlan(BaseModel):
    day: int
    date: Optional[str] = None
    theme: str = ""
    stops: list[ItineraryStop] = Field(default_factory=list)
    total_walking_km: float = 0.0
    total_cost_usd: float = 0.0
    cluster_id: Optional[int] = None


class ItineraryScore(BaseModel):
    total: float
    preference_alignment: float
    spatial_efficiency: float
    temporal_feasibility: float
    diversity: float


class Itinerary(BaseModel):
    intent: StructuredIntent
    days: list[DayPlan]
    score: ItineraryScore
    anchors: list[POI] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ─── API Responses ────────────────────────────────────────────────────────────

class PlanResponse(BaseModel):
    success: bool
    itinerary: Optional[Itinerary] = None
    error: Optional[str] = None


class IntentResponse(BaseModel):
    success: bool
    intent: Optional[StructuredIntent] = None
    error: Optional[str] = None


class POIListResponse(BaseModel):
    success: bool
    pois: list[POI] = Field(default_factory=list)
    total: int = 0
    error: Optional[str] = None
