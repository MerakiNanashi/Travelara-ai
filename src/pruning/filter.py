from __future__ import annotations

import math
from rapidfuzz import fuzz
import unicodedata
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


from src.shared.utils.calcs import sigmoid
from src.shared.schemas import (
    StructuredIntent,
    POI,
    _FilterConfig,
    UtilityScore
)
from src.shared.adapters import poi_adapter

BAD_TERMS = {"atm","parking","bus", "stop","toilet","restroom","taxi","stand","charging","station"}
TOURISM_TAG_WEIGHTS = {
    "tourism": 0.4,
    "tourism.attraction": 1.0,
    "tourism.sights": 1.0,
    "tourism.museum": 0.8,
    "building.tourism": 0.6,
    "historic": 0.8,
    "heritage": 0.8,
    "entertainment.museum": 0.8,
    "entertainment.culture": 0.6,
    "entertainment.culture.gallery": 0.5
}

class Filter:

    def __init__(self,
                 intent: StructuredIntent,
                 pois: list[POI],
                 config: _FilterConfig):
        
        self.intent = intent
        self.pois = pois
        self.config = config

        # Precompute user-derived state
        self.must_visit = {place.lower()
            for place in intent.constraints.must_visit
        }

        self.preference_weights = {pref.category.lower(): pref.weight
            for pref in intent.preferences
        }

        self.user_profile = self._build_user_profile()

        # Precompute POI-derived state
        self.normalized_names = {
            poi.id: self.normalize_name(poi.name)
            for poi in pois
        }

        self.tag_text = {
            poi.id: " ".join([poi.category, *poi.tags]).lower()
            for poi in pois
        }

        self.poi_profiles = {
            poi.id: self._build_poi_profile(poi)
            for poi in pois
        }

        self.external_link_counts = {
            poi.id: len(poi.external_links)
            for poi in pois
        }

        self.lower_links = {
            poi.id: [link.lower() for link in poi.external_links]
            for poi in pois
        }

    @staticmethod
    def normalize_name(name: str) -> str:
        return unicodedata.normalize("NFKC", name).lower().strip()
    
    @staticmethod
    def _is_same_poi(name1: str, name2: str) -> bool:
        return fuzz.token_sort_ratio(name1, name2) >= 90

    @staticmethod
    def _build_poi_profile(poi: POI) -> str:
        return " ".join([poi.name, poi.category, *poi.tags])
    
    def _score_external(self, poi: POI) -> float:
        """
        Distribution from a sample size of 800+ POIs:
            0 links: 69.53%
            1 links: 27.61%
            2 links: 1.37%
            3 links: 0.87%
            4 links: 0.62%
        Hence, cutoff at 3, since above 3 only ~1.5% data exists.
        """
        return math.log1p(self.external_link_counts[poi.id]) / math.log1p(3)
    
    def _score_wiki(self, poi) -> float: #untested for now
        score = 0.0
        for link in self.lower_links[poi.id]:
            link = link.lower()
            if "wikidata.org" in link:
                score += 2.0
            elif "wikipedia.org" in link:
                score += 1.5
            elif "commons.wikimedia.org" in link:
                score += 1.0
            else:
                score += 0.5
        return min(math.log1p(score) / math.log1p(5), 1.0)
    
    def _score_downBT(self, name: str) -> float:
        name_lower = name.lower()
        if any(mv in name_lower or name_lower in mv for mv in self.must_visit): 
            return 1.0
        for term in BAD_TERMS:
            if term in name_lower: 
                return 0.0
        return 1.0
    
    def _build_user_profile(self) -> str:
        profile: list[str] = []
        for category, weight in self.preference_weights.items():
            if weight > 0.3:
                profile.extend([category] * max(1, int(weight * 10)))
        profile.extend(self.must_visit)
        return " ".join(profile)

    def _score_source(self, poi: POI) -> float:
        name = self.normalized_names[poi.id]

        for other in self.pois:
            if other.id == poi.id:
                continue

            if self._is_same_poi(
                name,
                self.normalized_names[other.id],
            ):
                return 1.0

        return 0.0
    
    def _score_tags(self, poi: POI) -> float:
        score = 0.0
        tag_text = self.tag_text[poi.id]

        for pref, weight in self.preference_weights.items():
            if pref in tag_text:
                score += weight

        for tag in poi.tags:
            tag = tag.lower()
            for tourism_tag, tourism_weight in TOURISM_TAG_WEIGHTS.items():
                if tourism_tag in tag:
                    score += tourism_weight

        return min(score, 3.0)
    
    def _semantic_scores(self) -> list[float]:
        corpus = [self.user_profile]
        corpus.extend(
            self.poi_profiles[poi.id]
            for poi in self.pois
        )

        X = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
        ).fit_transform(corpus)

        return cosine_similarity(
            X[0],
            X[1:],
        )[0].tolist()

    def score_filter(self) -> list[UtilityScore]:
        semantic_scores = self._semantic_scores()
        scores: list[UtilityScore] = []

        for poi, semantic_score in zip(self.pois, semantic_scores):
            score_bt = self._score_downBT(poi.name)
            score_source = self._score_source(poi)
            score_external = self._score_external(poi)
            score_tags = self._score_tags(poi)
            score_wiki = self._score_wiki(poi)

            raw_score = (
                self.config.name_weight * score_bt
                + self.config.source_weight * score_source
                + self.config.tag_weight * score_tags
                + self.config.link_weight * score_external
                + self.config.semantic_weight * semantic_score
                + self.config.wiki_weight * score_wiki
            )

            scores.append(
                UtilityScore(
                    name=score_bt,
                    source=score_source,
                    tags=score_tags,
                    external_links=score_external,
                    wiki=score_wiki,
                    semantic=semantic_score,
                    raw=raw_score,
                    overall=sigmoid(raw_score - self.config.sigmoid_offset),
                )
            )

        return scores
    
    def score_pois(self) -> list[POI]:
        scores = self.score_filter()
        scored_pois = []
        for poi, score in zip(self.pois, scores):
            scored_pois.append(
                POI(
                    **poi.model_dump(exclude={"utility"}),
                    utility=score
                )
            )
        self.scored_pois = scored_pois

        return poi_adapter.sort_by_utility(self.scored_pois)