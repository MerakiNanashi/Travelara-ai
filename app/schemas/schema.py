from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─── Structured Intent (Extractor output) ─────────────────────────────────────

class PreferenceType(str, Enum):
    MUSEUMS = "museums"
    FOOD = "food"
    NIGHTLIFE = "nightlife"
    NATURE = "nature"
    SHOPPING = "shopping"
    ARTS = "arts"
    HISTORY = "history"
    WELLNESS = "wellness"


class Preference(BaseModel):
    category: PreferenceType | None = None
    name: str | None = None
    type: str = Field(pattern="^(objective|subjective)$")     # objective -> retrieval/filtering  subjective -> downstream scoring, ranking, anchor selection, etc.
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: int = Field(default=2, ge=1, le=5)
    status: str = Field(pattern="^(explicit|inferred|clarification)$")
    evidence: str | None = None

class Constraints(BaseModel):
    walking_limit_km: float = 10.0
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    budget_per_day_usd: Optional[float] = None

class StructuredIntent(BaseModel):
    """
Future Updates:

1. Categorize user into new_user, active_user, recurring_user, etc.
2. Any places visited before? / Level of hiddeness idk?
3. Triggers for more info extraction from user
4. 
    """
    destination: str
    days: int
    stay_location: Optional[str] = None
    is_international: bool
    budget: str  # low / medium / high
    preferences: list[Preference]
    constraints: Constraints
    start_date: Optional[str] = None

class AnchorScore(BaseModel):
    semantic_score: float = 0.0
    representative_score: float = 0.0
    expansion_score: float = 0.0
    connectivity_score: float = 0.0
    importance_score: float = 0.0
    overall_anchor: float = 0.0
# ─── POI ──────────────────────────────────────────────────────────────────────

class POI(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    category: str
    tags: list[str] = Field(default_factory=list)
    popularity_score: float | None = None
    opening_hours: dict | str | None = None
    external_links: list[str] = Field(default_factory=list)
    rating: float | None = None
    reviews: int | None = None
    address: str = ""
    pincode: str = ""
    wiki_and_media: dict = Field(default_factory=dict)
    distance: int | None = None
    source: str = "foursquare"

    # Scoring fields (populated during planning)
    utility_score: Optional[QualityScore] = None
    anchor_score: AnchorScore = Field(default_factory=AnchorScore)
    wiki_enrichment: str | dict | list | None = None


# ─── API Responses ────────────────────────────────────────────────────────────

class IntentResponse(BaseModel):
    success: bool
    intent: Optional[StructuredIntent] = None
    error: Optional[str] = None


class POIListResponse(BaseModel):
    success: bool
    pois: list[POI] = Field(default_factory=list)
    total: int = 0
    error: Optional[str] = None


class QualityScore(BaseModel):
    id: str
    name_score: float = 1.0
    source_score: float = 0.0
    tag_score: float = 0.0
    external_link_score: float = 0.0
    wiki_score: float = 0.0
    semantic_score: float = 0.0
    overall_score: float = 0.0
    raw_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class ClusterMetrics(BaseModel):
    cluster_id: int
    sum_score: float
    max_score: float
    p90_score: float
    size: int
    density: float
    survival_score: float
    protected: bool


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
