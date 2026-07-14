"""
The ONLY module allowed to know StructuredIntent's internal shape
(FieldState wrappers, Preference objects, Constraints). Every consumer —
providers, filter, score, cluster — calls these functions instead of
touching `.value`, `.constraints.walking_limit_km`, `pref.category`, etc.
directly.
"""
from __future__ import annotations
from src.shared.schemas import StructuredIntent, Preference, PreferenceType


# --- resolved scalars ------------------------------------------------------

def destination(intent: StructuredIntent) -> str:
    value = intent.destination.value
    if value is None:
        raise ValueError("destination requested before it was resolved")
    return str(value)


def trip_days(intent: StructuredIntent, default: int = 3) -> int:
    value = intent.days.value
    return int(value) if value is not None else default


def start_date(intent: StructuredIntent) -> str | None:
    value = intent.start_date.value
    return str(value) if value is not None else None


def stay_location(intent: StructuredIntent) -> str | None:
    value = intent.stay_location.value
    return str(value) if value is not None else None


def is_international(intent: StructuredIntent, default: bool = False) -> bool:
    value = intent.is_international.value
    return bool(value) if value is not None else default


def budget_tier(intent: StructuredIntent, default: str = "medium") -> str:
    value = intent.budget.value
    return str(value) if value is not None else default


# --- constraints ------------------------------------------------------------

def walking_limit_km(intent: StructuredIntent, default: float = 10.0) -> float:
    limit = intent.constraints.walking_limit_km
    return limit if limit else default


def budget_per_day_usd(intent: StructuredIntent) -> float | None:
    value = intent.constraints.budget_per_day_usd
    return value if value else None


def must_visit_names(intent: StructuredIntent) -> list[str]:
    return [m.lower() for m in intent.constraints.must_visit]


def avoid_categories(intent: StructuredIntent) -> list[str]:
    return [a.lower() for a in intent.constraints.avoid]


# --- preferences -------------------------------------------------------------

def preferences(intent: StructuredIntent) -> list[Preference]:
    """Escape hatch for callers that genuinely need the full Preference
    objects (priority, evidence, status). Prefer the weight-dict helpers
    below wherever possible — they're what most callers actually want."""
    return list(intent.preferences)


def objective_category_weights(intent: StructuredIntent) -> dict[str, float]:
    """
    category -> weight, objective preferences only. This is what
    retrieval uses to pick provider categories — subsumes the old
    internals.preferences_to_legacy(), which took a raw Preference list;
    now callers never need to extract that list from intent themselves.
    Duplicate categories keep the highest weight.
    """
    weights: dict[str, float] = {}
    for pref in intent.preferences:
        if pref.type != PreferenceType.OBJECTIVE or pref.category is None:
            continue
        weights[pref.category.value] = max(weights.get(pref.category.value, 0.0), pref.weight)
    return weights


def all_preference_weights(intent: StructuredIntent) -> dict[str, float]:
    """category -> weight for every preference with a resolved category,
    objective or subjective. Used by scoring stages (filter.py, score.py)
    that want the full profile, not just the retrieval-relevant slice."""
    weights: dict[str, float] = {}
    for pref in intent.preferences:
        if pref.category is None:
            continue
        weights[pref.category.value] = max(weights.get(pref.category.value, 0.0), pref.weight)
    return weights


# --- readiness / status -------------------------------------------------------

def is_ready_for_planning(intent: StructuredIntent) -> bool:
    return intent.ready_for_planning


def unresolved_fields(intent: StructuredIntent) -> list[str]:
    return list(intent.ambiguities)


def clarification_text(intent: StructuredIntent) -> str | None:
    q = intent.clarification_question
    return q.question if q.question.strip() else None