from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from dataclasses import dataclass
from .scores import UtilityScore, AnchorScore, ClusterScore


# ───────────────────────────── Internal Schemas : Clustering  ───────────────────────────── #

@dataclass
class WikiEnrichment:
    en_name: str | None = None
    description: str | None = None
    img_url: str | None = None


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
    wiki_enrichment: WikiEnrichment = Field(default_factory=WikiEnrichment)
    distance_m: float | None = None
    source: str = ""

    utility: UtilityScore = Field(default_factory=UtilityScore)   # required, not optional — guaranteed present
    cluster_id: int | None = None
    anchor: AnchorScore = Field(default_factory=AnchorScore)
    rank: int | None = None

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @property
    def get_coordinates(self) -> tuple[float, float]:
        return self.lat, self.lon

    @property
    def normalized_name(self) -> str:
        return self.name.casefold().strip()
    
    # @property
    # def 

class Cluster(BaseModel):
    cluster_id: int
    size: int = 0
    centroid: tuple[float, float] | None = None
    cluster_score: ClusterScore = Field(default_factory=ClusterScore)
    selected: bool = False
    members: list[POI] = Field(default_factory=list)
    rank: int = 0