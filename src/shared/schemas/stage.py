from __future__ import annotations

from pydantic import BaseModel
from dataclasses import dataclass
from typing import Any
from .scores import ClusterScore
# ───────────────────────────── Stage Result ───────────────────────────── #

class ClusterSelectionResult(BaseModel):
    selected_pois: Any | None = None
    selected_clusters: list[ClusterScore] | None = None
    cluster_map: dict[str, int] | None = None
    threshold: float | None = None

class CandidateSelectionResult(BaseModel):
    cluster: Any | None = None
    anchor: Any | None = None
    pois: Any | None = None

@dataclass
class StageContext:
    config: Any
    debugger: Any
    settings: Any
