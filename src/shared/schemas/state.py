from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .request import PlanningRequest
from .intent import StructuredIntent
from .candidate import POI, Cluster
from .itinerary import Itinerary
from .enums import Stage

# ───────────────────── Runtime Metadata ─────────────────────
class PipelineMetadata(BaseModel):
    run_id: str | None = None
    current_stage: Stage = Stage.INTENT
    completed_stages: list[Stage] = Field(default_factory=list)
    failed_stages: list[Stage] = Field(default_factory=list)
    retries: int = 0

# ───────────────────── Artifacts ─────────────────────
class PipelineArtifacts(BaseModel):
    """
    clusters -> dict of cluster_id & pois in cluster equivalent to cluster map but reverse  
    candidate_selection -> #  
    cluster_map -> poi: cluster no.  
    """
    clusters: dict[int, Cluster] = Field(default_factory=dict)
    candidate_selection: Any | None = None
    cluster_map: dict[str, int] = Field(default_factory=dict)

# ───────────────────── Planning State (Global State) ─────────────────────
class PlanningState(BaseModel):
    """
    Shared mutable state passed through the planning pipeline.  

    Pipeline stages:  
        0. Initialization - request  
        1. Intent Extraction - intent  
        2. Retrieval - raw_pois  
        3. Scoring & Clustering - scored_pois, clustered_pois  
        4. Pruning - selected_pois  
        5. Enrichment - enriched_pois  
        6. Re-ranking - ranked_pois  
        7. Candidate Selection - candidate_pois  
        8. Itinerary Generation - itinerary  

    Additional state:  
        - artifacts: Intermediate outputs produced by pipeline stages.  
        - metadata: Execution metrics and diagnostic information.  
        - cache: Temporary shared storage between stages.
    """
    request: PlanningRequest
    intent: StructuredIntent | None = None

    raw_pois: list[POI] = Field(default_factory=list)
    scored_pois: list[POI] = Field(default_factory=list)
    clustered_pois: list[POI] = Field(default_factory=list)
    selected_pois: list[POI] = Field(default_factory=list)
    enriched_pois: list[POI] = Field(default_factory=list)
    ranked_pois: list[POI] = Field(default_factory=list)
    candidate_pois: list[POI] = Field(default_factory=list)

    itinerary: Itinerary | None = None

    artifacts: PipelineArtifacts = Field(default_factory=PipelineArtifacts)
    metadata: PipelineMetadata = Field(default_factory=PipelineMetadata)
    cache: dict[str, Any] = Field(default_factory=dict)