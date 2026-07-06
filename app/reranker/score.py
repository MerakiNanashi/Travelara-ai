from __future__ import annotations

from app.details.wikidata import enrich_selected_pois

from app.reranker.anchor import AnchorScorer
from app.reranker.poolBuilder import CandidatePoolBuilder
from app.reranker.semantic import SemanticScorer

from app.schemas import (
    ClusterSelectionResult,
    CandidateSelectionResult,
    StructuredIntent,
)


class CandidateScorer:

    def __init__(
        self,
        semantic: SemanticScorer | None = None,
        anchor: AnchorScorer | None = None,
        selector: CandidatePoolBuilder | None = None,
    ):
        self.semantic = semantic or SemanticScorer()
        self.anchor = anchor or AnchorScorer()
        self.selector = selector or CandidatePoolBuilder()
        
    async def score(
        self,
        clustering: ClusterSelectionResult,
        intent: StructuredIntent,
    ) -> CandidateSelectionResult:

        pois = clustering.selected_pois

        enrichable = [
            poi
            for poi in pois
            if poi.wiki_and_media
            and poi.wiki_and_media.get("wikidata")
        ]

        await enrich_selected_pois(enrichable)

        semantic_scores = self.semantic.score(
            pois,
            intent,
        )

        for poi, score in zip(pois, semantic_scores):
            poi.utility.semantic = float(score)

        anchors = self.anchor.score(
            pois,
            clustering.cluster_map,
        )

        return self.selector.select(
            pois=anchors,
            selected_clusters=clustering.selected_clusters,
            cluster_map=clustering.cluster_map,
            days=intent.days.value,
        )