from enum import Enum


# ---------- Enums ----------

class BudgetLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PreferenceType(str, Enum):
    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"


class PreferenceStatus(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    CLARIFICATION = "clarification"


class IntentStatus(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"


class PreferenceCategory(str, Enum):
    MUSEUMS = "museums"
    FOOD = "food"
    NIGHTLIFE = "nightlife"
    NATURE = "nature"
    SHOPPING = "shopping"
    ARTS = "arts"
    HISTORY = "history"
    WELLNESS = "wellness"

class Stage(str, Enum):
    INTENT = "intent_extraction"
    RETRIEVAL = "retrieval"
    SCORING = "scoring"
    CLUSTERING = "clustering"
    ENRICHMENT = "enrichment"
    ITINERARY = "itinerary"