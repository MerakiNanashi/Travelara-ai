from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.schemas.request import PlanningRequest
from app.schemas.intent import StructuredIntent
from app.schemas.candidate import POI, ScoredPOI, ClusteredPOI, PlannedPOI, ClusterSelectionResult
from app.schemas.itinerary import Itinerary
from app.schemas.enums import Stage


# ───────────────────── Runtime Metadata ─────────────────────
class PipelineMetadata(BaseModel):
    run_id: str | None = None
    current_stage: Stage = Stage.INTENT
    completed_stages: list[Stage] = Field(default_factory=list)
    failed_stages: list[Stage] = Field(default_factory=list)
    retries: int = 0

# ───────────────────── Graph / Clustering ─────────────────────

class Cluster(BaseModel):
    cluster_id: int | None = None
    size: int = 0
    centroid: tuple[float, float] | None = None
    density: float = 0.0
    sum_score: float = 0.0
    max_score: float = 0.0
    p90_score: float = 0.0
    survival_score: float = 0.0
    protected: bool = False
    poi_ids: list[str] = Field(default_factory=list)

# ───────────────────── Review ─────────────────────
class PlanningIssue(BaseModel): # Future use
    stage: str | None = None
    severity: str | None = None
    message: str | None = None
    repairable: bool = True

# ───────────────────── Artifacts ─────────────────────
class PipelineArtifacts(BaseModel):
    retrieval_query: Any | None = None
    retrieval_raw: Any | None = None
    cluster_map: dict[str, int] = Field(default_factory=dict)
    distance_matrix: Any | None = None
    scheduler_metadata:  Any | None = None
    reviewer_metadata:  Any | None = None
    graph: Any | None = None

# ───────────────────── Planning State (Global State) ─────────────────────
class PlanningState(BaseModel):
    request: PlanningRequest
    intent: StructuredIntent | None = None
    raw_pois: list[POI] = Field(default_factory=list)
    scored_pois: list[ScoredPOI] = Field(default_factory=list)
    clustered_pois: list[ClusteredPOI] = Field(default_factory=list)
    planned_pois: list[PlannedPOI] = Field(default_factory=list)
    clusters: dict[int, Cluster] = Field(default_factory=dict)
    cluster_selection: ClusterSelectionResult = Field(default_factory=ClusterSelectionResult)
    candidate_selection: Any | None = None
    
    anchor_ids: list[str] = Field(default_factory=list)
    itinerary: Itinerary | None = None
    issues: list[PlanningIssue] = Field(default_factory=list)

    artifacts: PipelineArtifacts = Field(default_factory=PipelineArtifacts)
    metadata: PipelineMetadata = Field(default_factory=PipelineMetadata)
    cache: dict[str, Any] = Field(default_factory=dict)
