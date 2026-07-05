from __future__ import annotations
import math
from app.schemas import UtilityScore
from rapidfuzz import fuzz
import unicodedata
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def sigmoid(x): return 1 / (1 + math.exp(-x))

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

def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).lower().strip()

class Filter:
    def __init__(self): pass

    @staticmethod
    def _is_same_poi(name1: str, name2: str) -> bool:
        return fuzz.token_sort_ratio(normalize_name(name1), normalize_name(name2)) >= 90

    @staticmethod
    def _score_downBT(name: str, intent) -> float:
        name_lower = name.lower()
        must_visit = {p.lower() for p in intent.constraints.must_visit}
        if any(mv in name_lower or name_lower in mv for mv in must_visit): return 1.0
        for term in BAD_TERMS:
            if term in name_lower: return 0.0
        return 1.0
    
    @staticmethod
    def _build_user_profile(intent):
        profile = []
        prefs = {pref.category: pref.weight for pref in intent.preferences}
        for k, v in prefs.items():
            if v > 0.3: # Same threshold as _get_top_preferences t - adjustable
                profile.extend([k] * max(1, int(v * 10)))

        profile.extend(intent.constraints.must_visit)

        return " ".join(profile)

    @staticmethod
    def _build_poi_profile(poi):
        return " ".join([
            poi.name,
            poi.category,
            *poi.tags
        ])

    def _score_source(self, poi, pois) -> float:
        for other in pois:
            if other.id == poi.id: continue
            if self._is_same_poi(other.name, poi.name): return 1.0
        return 0.0

    def _score_external(self, poi) -> float:
        """
        Distribution from a sample size of 800+ POIs:
            0 links: 69.53%
            1 links: 27.61%
            2 links: 1.37%
            3 links: 0.87%
            4 links: 0.62%
        Hence, cutoff at 3, since above 3 only ~1.5% data exists.
        """
        return math.log1p(len(poi.external_links)) / math.log1p(3)

    def _score_wiki(self, poi) -> float: #untested for now
        score = 0.0
        for link in poi.external_links:
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
    
    def _score_tags(self, poi, intent) -> float:
        score = 0.0
        prefs = {k.lower(): v for k, v in [(pref.category, pref.weight) for pref in intent.preferences]}
        tag_text = " ".join([poi.category, *poi.tags]).lower()
        for pref, weight in prefs.items():
            if pref in tag_text:
                score += weight
        for tag in poi.tags:
            tag_lower = tag.lower()
            for tourism_tag, tourism_weight in TOURISM_TAG_WEIGHTS.items():
                if tourism_tag in tag_lower:
                    score += tourism_weight
        return min(score, 3.0)
    
    def _semantic_scores(self, pois, intent):
        user_profile = self._build_user_profile(intent)
        poi_profiles = [self._build_poi_profile(poi) for poi in pois]

        corpus = [user_profile] + poi_profiles
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english"
        )
        X = vectorizer.fit_transform(corpus)
        user_vec = X[0]
        poi_vecs = X[1:]
        scores = cosine_similarity(user_vec,poi_vecs)[0]
        return {
            poi.id: float(score)
            for poi, score in zip(pois, scores)
        }

    def score_filter(self, pois, intent) -> list[UtilityScore]:
        poi_scores = []
        semantic_scores = self._semantic_scores(pois, intent)
        for poi in pois:
            score_BT = self._score_downBT(poi.name, intent)
            score_source = self._score_source(poi, pois)
            score_external = self._score_external(poi)
            score_tags = self._score_tags(poi, intent)
            score_wiki = self._score_wiki(poi)
            score_semantic = semantic_scores.get(poi.id, 0.0)

            raw_score_overall = (1.0 * score_BT) + (3.0 * score_source) + (1.5 * score_tags) + (1.0 * score_external) + (3.0 * score_semantic) + (1.5 * score_wiki)
            norm_score_overall = sigmoid(raw_score_overall - 3.0)

            poi_scores.append(
                UtilityScore(
                    name_score=score_BT,
                    source_score=score_source,
                    tag_score=score_tags,
                    external_link_score=score_external,
                    wiki_score=score_wiki,
                    semantic_score=score_semantic,
                    overall_score=norm_score_overall,
                    raw_score=raw_score_overall
                )
            )

        return poi_scores

if __name__ == '__main__':
    # Example usage
    filter_obj = Filter()
    # poi_scores = filter_obj.score_filter(pois, intent)