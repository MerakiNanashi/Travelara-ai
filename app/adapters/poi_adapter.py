"""
The ONLY module allowed to know POI/ScoredPOI/ClusteredPOI/AnchorPOI's
nested field shapes. cluster.py, score.py, and provider-side filtering
call these instead of reaching into `.utility.raw`, `.anchor.overall`,
`.wiki_and_media`, `.wiki_enrichment` directly.
"""
from __future__ import annotations
from collections import defaultdict
from app.schemas import POI, ScoredPOI, ClusteredPOI, AnchorPOI


# --- scores ------------------------------------------------------------------

def utility_raw(pois: list[ScoredPOI]) -> dict[str, float]:
    return {p.id: p.utility.raw for p in pois}


def utility_overall(pois: list[ScoredPOI]) -> dict[str, float]:
    return {p.id: p.utility.overall for p in pois}


def anchor_overall(pois: list[AnchorPOI]) -> dict[str, float]:
    return {p.id: p.anchor.overall for p in pois}


# --- identity / spatial --------------------------------------------------------

def coordinates(pois: list[POI]) -> dict[str, tuple[float, float]]:
    return {p.id: (p.lat, p.lon) for p in pois}


def categories(pois: list[POI]) -> dict[str, str]:
    return {p.id: p.category for p in pois}


def popularity(pois: list[POI]) -> dict[str, float]:
    return {p.id: (p.popularity_score or 0.0) for p in pois}


# --- enrichment ---------------------------------------------------------------
# NOTE: POI.wiki_enrichment is currently typed `str | None`, but
# wikidata.py assigns a dict (`{en_name, description, img_url}`). This
# defensive isinstance check exists SPECIFICALLY so no caller has to know
# about that mismatch — once wiki_enrichment becomes a proper
# WikiEnrichment model, this function collapses to one line and every
# caller of it is unaffected.

def wiki_description(poi: POI) -> str:
    enrichment = poi.wiki_enrichment
    if isinstance(enrichment, dict):
        return enrichment.get("description") or ""
    return ""


def wiki_display_name(poi: POI) -> str:
    """English Wikidata label if present, else the provider's raw name."""
    enrichment = poi.wiki_enrichment
    if isinstance(enrichment, dict):
        en = enrichment.get("en_name")
        if en and str(en).strip():
            return str(en).strip()
    return poi.name


def has_wikidata_qid(poi: POI) -> bool:
    return bool(poi.wiki_and_media and poi.wiki_and_media.get("wikidata"))


# --- grouping ------------------------------------------------------------------
# cluster_id is a flat, stable int (not nested/volatile) — this helper
# exists for reason #2 (centralizing repeated derivation), not #1
# (hiding volatile shape). The same defaultdict-grouping loop appeared
# independently in cluster.py and score.py; one bug fix here now fixes
# both call sites.

def group_by_cluster(pois: list[ClusteredPOI]) -> dict[int, list[ClusteredPOI]]:
    grouped: dict[int, list[ClusteredPOI]] = defaultdict(list)
    for poi in pois:
        grouped[poi.cluster_id].append(poi)
    return dict(grouped)

def sort_by_utility(pois: list[ScoredPOI]) -> list[ScoredPOI]:
    return sorted(
        pois,
        key=lambda poi: poi.utility.raw,
        reverse=True,
    )