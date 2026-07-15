from __future__ import annotations

from dataclasses import dataclass

# ───────────────────────────── Scoring/Enrichment - for POI ───────────────────────────── #

@dataclass
class UtilityScore:
    name: float = 1.0
    source: float = 0.0
    tags: float = 0.0
    external_links: float = 0.0
    wiki: float = 0.0
    semantic: float = 0.0
    raw: float = 0.0
    overall: float = 0.0

@dataclass
class AnchorScore:
    semantic: float = 0.0
    representative: float = 0.0
    expansion: float = 0.0
    connectivity: float = 0.0
    importance: float = 0.0
    overall: float = 0.0

@dataclass
class ClusterScore:
    size: int
    sum_score: float
    max_score: float
    p90_score: float
    score_avg: float
    diversity: float
    survival_score: float
    protected: bool