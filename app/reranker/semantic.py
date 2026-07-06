from __future__ import annotations

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.schemas import ClusteredPOI, StructuredIntent


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
        model_name: str = "BAAI/bge-m3",
        device: str | None = None,
        batch_size: int = 128,
    ):
        if SemanticScorer._model is None:
            SemanticScorer._model = SentenceTransformer(
                model_name,
                device=device,
            )

        self.model = SemanticScorer._model
        self.batch_size = batch_size

    @staticmethod
    def _build_user_profile(
        intent: StructuredIntent,
    ) -> str:
        preferences = ", ".join(
            f"{pref.category} ({pref.weight:.2f})"
            for pref in intent.preferences
            if pref.weight > 0
        )

        return (
            f"Destination: {intent.destination.value}\n"
            f"Stay: {intent.stay_location.value}\n"
            f"Budget: {intent.budget.value}\n"
            f"Trip Length: {intent.days.value} days\n"
            f"Walking Limit: {intent.constraints.walking_limit_km} km\n"
            f"Interests: {preferences}"
        )

    @staticmethod
    def _build_poi_documents(
        pois: list[ClusteredPOI],
    ) -> list[str]:
        return [
            (
                f"Name: {poi.name}\n"
                f"Category: {poi.category}\n"
                f"Tags: {', '.join(poi.tags or [])}\n"
                f"Description: {(poi.wiki_enrichment or {}).get('description', '')}"
            )
            for poi in pois
        ]

    def score(
        self,
        pois: list[ClusteredPOI],
        intent: StructuredIntent,
    ) -> np.ndarray:
        if not pois:
            return np.empty(0, dtype=np.float32)

        user_document = self._build_user_profile(intent)
        poi_documents = self._build_poi_documents(pois)

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

        return similarities.cpu().numpy()