from __future__ import annotations

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from src.shared.schemas import StructuredIntent, POI, AnchorScore

# Builds semantic scores for all pois & user profile
# Stage calls SemanticScorer.score -> Fill anchor values.
class SemanticScorer:
    """
    High-performance semantic scorer.

    Responsibilities
    ----------------
    • Build user profile
    • Build POI documents
    • Encode with BGE-M3
    • Return similarity scores

    No mutation.
    No enrichment.
    No anchor logic.
    """

    _model: SentenceTransformer | None = None

    def __init__(
        self,
        pois: list[POI],
        intent: StructuredIntent,
        model_name: str = "BAAI/bge-m3",
        device: str | None = None,
        batch_size: int = 128
    ):
        if SemanticScorer._model is None:
            SemanticScorer._model = SentenceTransformer(
                model_name,
                device=device,
            )

        self.model = SemanticScorer._model
        self.batch_size = batch_size
        self.pois = pois
        self.intent = intent

    def _build_user_profile(
        self
    ) -> str:
        preferences = ", ".join(
            f"{pref.category} ({pref.weight:.2f})"
            for pref in self.intent.preferences
            if pref.weight > 0
        )

        return (
            f"Destination: {self.intent.destination.value}\n"
            f"Stay: {self.intent.stay_location.value}\n"
            f"Budget: {self.intent.budget.value}\n"
            f"Trip Length: {self.intent.days.value} days\n"
            f"Walking Limit: {self.intent.constraints.walking_limit_km} km\n"
            f"Interests: {preferences}"
        )

    def _build_poi_documents(
        self
    ) -> list[str]:
        return [
            (
                f"Name: {poi.name}\n"
                f"Category: {poi.category}\n"
                f"Tags: {', '.join(poi.tags or [])}\n"
                f"Description: {poi.wiki_enrichment.description if poi.wiki_enrichment else ''}"
            )
            for poi in self.pois
        ]

    def score(self) -> list[POI]:
        if not self.pois:
            return []

        user_document = self._build_user_profile()
        poi_documents = self._build_poi_documents()

        with torch.inference_mode():
            user_embedding = self.model.encode(
                user_document,
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            poi_embeddings = self.model.encode(
                poi_documents,
                convert_to_tensor=True,
                normalize_embeddings=True,
                batch_size=self.batch_size,
                show_progress_bar=False,
            )

            similarities = torch.matmul(
                poi_embeddings,
                user_embedding,
            )

            similarities.add_(1.0).mul_(0.5)

        scores = similarities.cpu().numpy()

        for poi, semantic in zip(self.pois, scores):
            if poi.anchor is None:
                poi.anchor = AnchorScore(
                    semantic=float(semantic),
                    representative=0.0,
                    expansion=0.0,
                    connectivity=0.0,
                    importance=0.0,
                    overall=0.0,
                )
            else:
                poi.anchor.semantic = float(semantic)

        return self.pois