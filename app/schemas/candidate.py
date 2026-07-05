from typing import Any
from pydantic import BaseModel, Field, ConfigDict


# ───────────────────────────── Scoring ───────────────────────────── #

class UtilityScore(BaseModel):
    name: float = 1.0
    source: float = 0.0
    tags: float = 0.0
    external_links: float = 0.0
    wiki: float = 0.0
    semantic: float = 0.0
    raw: float = 0.0
    overall: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class AnchorScore(BaseModel):
    semantic: float = 0.0
    representative: float = 0.0
    expansion: float = 0.0
    connectivity: float = 0.0
    importance: float = 0.0
    overall: float = 0.0


# ───────────────────────────── POI ───────────────────────────── #

class POI(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    category: str
    tags: list[str] = Field(default_factory=list)
    popularity_score: float | None = None
    rating: float | None = None
    reviews: int | None = None
    opening_hours: dict[str, Any] | str | None = None
    address: str = ""
    pincode: str = ""
    external_links: list[str] = Field(default_factory=list)
    wiki_and_media: dict[str, Any] = Field(default_factory=dict)
    wiki_enrichment: str | None = None
    distance_m: float | None = None
    source: str = ""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class ScoredPOI(POI):
    utility: UtilityScore   # required, not optional — guaranteed present

class ClusteredPOI(ScoredPOI):
    cluster_id: int

class AnchorPOI(ClusteredPOI):
    anchor: AnchorScore
    rank: int | None = None

class PlannedPOI(AnchorPOI):
    selected_as_anchor: bool = False
    selected_for_itinerary: bool = False
    notes: list[str] = Field(default_factory=list)