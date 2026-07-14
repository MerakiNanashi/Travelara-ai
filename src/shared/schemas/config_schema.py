from __future__ import annotations

from dataclasses import dataclass

@dataclass
class _ClusteringConfig:
    min_cluster_size: int = 5
    min_samples: int = 2

@dataclass
class _PruningConfig:
    diversity_weight: float = 0.15
    pruning_percentile: float = 60
    protected_top_n: int = 50

@dataclass(frozen=True)
class _WikipediaConfig:
    user_agent: str = "Travelara/0.1"
    accept: str = "application/json"
    timeout: int = 30
    concurrency: int = 10
    rate_limit: tuple[int, int] = (200, 60)
    follow_redirects: bool = True
    lang: str = "en"
    maxlag: int = 5
    batch_size: int = 50

@dataclass
class _ProviderConfig:
    source: str = "GA"
    taxonomy_path: str = ""
    url: str = ""
    limit: int = 499

@dataclass
class _ExtractorConfig:
    prompt_version: str = "0.1.0"
    temperature: float = 0.1
    max_turns: int = 3
    active_model: str = "gemini-3.1-flash-lite"
    fallback_model: str = "gemini-2.5-flash-lite"
    url: str = "https://generativelanguage.googleapis.com/v1beta/interactions"
    timeout: float = 60.0
    thinking_level: str = "minimal"