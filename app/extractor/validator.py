"""
NEEDS TO BE FIXED
validator.py
────────────
Everything about turning a raw Gemini JSON draft into a trustworthy,
merged StructuredIntent lives here:
  - parsing the raw response text (standardized failure modes)
  - casting stringly-typed field values into their real types
  - merging a new draft on top of the previous turn's StructuredIntent
  - computing missing_required / ambiguities / clarification_queue /
    ready_for_planning
  - the turn-cap fallback (max 3 turns → force-resolve with defaults)

extractor.py should never touch raw dicts or do type-casting itself —
it only calls into here.
"""
from __future__ import annotations

import json
from datetime import date

from app.schemas.enums import IntentStatus, PreferenceCategory, PreferenceType, PreferenceStatus
from app.schemas.intent import (
    StructuredIntent,
    FieldState,
    Preference,
    Constraints,
    ClarificationQuestion,
)

MAX_TURNS = 3
REQUIRED_FIELDS = ["destination", "days", "budget", "is_international"]
ALL_FIELDS = ["destination", "days", "start_date", "stay_location",
              "is_international", "budget"]
FALLBACK_DEFAULTS = {
    "days": 3,
    "budget": "medium",
    "is_international": False,
}

# ─────────────────────────── Errors ─────────────────────────────────────── #

class ExtractionError(Exception):
    """Base class for all standardized extraction failures."""
    code = "extraction_error"


class ExtractionParseError(ExtractionError):
    """Gemini returned text that isn't valid JSON at all."""
    code = "parse_error"


class ExtractionSchemaError(ExtractionError):
    """Gemini returned valid JSON but it doesn't match the expected shape."""
    code = "schema_error"

class ExtractionServiceError(ExtractionError):
    """The Gemini call itself failed (network, auth, rate limit, timeout)."""
    code = "service_error"


# ─────────────────────────── Parsing ─────────────────────────────────────── #

def parse_gemini_response(raw_text: str) -> dict:
    """Parse raw Gemini text into a dict. Since we request
    responseMimeType=application/json, markdown fences shouldn't appear —
    but we defensively strip them anyway for robustness against model drift.
    """
    if not raw_text or not raw_text.strip():
        raise ExtractionParseError("Empty response from model.")

    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionParseError(f"Malformed JSON from model: {e}") from e

    if not isinstance(data, dict):
        raise ExtractionSchemaError("Top-level response is not a JSON object.")

    missing_top_level = [
        k for k in ("destination", "days", "budget", "preferences", "constraints")
        if k not in data
    ]
    if missing_top_level:
        raise ExtractionSchemaError(
            f"Response missing required top-level keys: {missing_top_level}"
        )
    return data


# ─────────────────────────── Casting helpers ─────────────────────────────── #

def _status(raw: str | None) -> IntentStatus:
    try:
        return IntentStatus(raw)
    except (TypeError, ValueError):
        return IntentStatus.UNKNOWN


def _cast_field(field_name: str, raw: dict | None) -> FieldState:
    """Cast one FIELD_SCHEMA dict into a typed FieldState, downgrading to
    'conflicting' on any cast failure instead of raising — a single bad
    field should never blow up the whole turn.
    """
    if not raw:
        return FieldState(value=None, status=IntentStatus.UNKNOWN, evidence="no value provided", required=False)

    status = _status(raw.get("status"))
    value = raw.get("value")
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), str) else ""

    if value is None or status == IntentStatus.UNKNOWN:
        return FieldState(value=None, status=status, evidence=evidence)

    try:
        if field_name == "days":
            v = int(float(value))
            if not (1 <= v <= 30):
                return FieldState(
                    value=value, status=IntentStatus.CONFLICTING,
                    evidence=f"days={value} out of realistic range (1-30)",
                )
            return FieldState(value=v, status=status, evidence=evidence)

        if field_name == "is_international":
            v = str(value).strip().lower() in ("true", "1", "yes")
            return FieldState(value=v, status=status, evidence=evidence)

        if field_name == "budget":
            v = str(value).strip().lower()
            if v not in ("low", "medium", "high"):
                return FieldState(
                    value=value, status=IntentStatus.CONFLICTING,
                    evidence=f"budget={value!r} not one of low/medium/high",
                )
            return FieldState(value=v, status=status, evidence=evidence)

        if field_name == "start_date":
            v = str(value).strip()
            try:
                date.fromisoformat(v)
            except ValueError:
                return FieldState(
                    value=v, status=IntentStatus.AMBIGUOUS,
                    evidence=f"start_date={v!r} not a resolvable ISO date",
                )
            return FieldState(value=v, status=status, evidence=evidence)

        # destination, stay_location: plain strings
        return FieldState(value=str(value).strip(), status=status, evidence=evidence)

    except (TypeError, ValueError) as e:
        return FieldState(
            value=value, status=IntentStatus.CONFLICTING,
            evidence=f"could not parse {field_name}={value!r}: {e}",
        )


def _cast_preferences(raw_list: list[dict] | None) -> list[Preference]:
    prefs: list[Preference] = []
    for item in raw_list or []:
        try:
            category = None
            if item.get("category"):
                try:
                    category = PreferenceCategory(item["category"])
                except ValueError:
                    category = None
            prefs.append(Preference(
                category=category,
                name=item.get("name") or "",
                type=PreferenceType(item.get("type") or "subjective"),
                weight=max(0.0, min(1.0, float(item.get("weight") or 0.5))),
                priority=max(1, min(5, int(item.get("priority") or 3))),
                status=PreferenceStatus(item.get("status") or "inferred"),
                evidence=item.get("evidence") or "",
            ))
        except Exception as e:
            # Malformed preference item — skip rather than fail the turn.
                print(item)
                print(repr(e))
                raise
    return prefs


def _cast_constraints(raw: dict | None) -> Constraints:
    raw = raw or {}

    return Constraints(
        walking_limit_km=raw.get("walking_limit_km") or 0.0,
        budget_per_day_usd=raw.get("budget_per_day_usd") or 0.0,
        must_visit=raw.get("must_visit") or [],
        avoid=raw.get("avoid") or [],
    )


def _cast_clarifications(raw_ques) -> ClarificationQuestion:
    if not raw_ques or not raw_ques.get("field") or not raw_ques.get("question"):
        return ClarificationQuestion(
            field="",
            question="",
            reason="",
            priority=1,
        )
    return ClarificationQuestion(
        field=raw_ques["field"] or "",
        question=raw_ques["question"] or "",
        reason=raw_ques.get("reason") or "",
        priority=raw_ques.get("priority") or 1,
    )


# ─────────────────────────── Merging ──────────────────────────────────────── #

def _merge_field(prev: FieldState | None, new: FieldState) -> FieldState:
    """Never let a resolved field regress to unknown just because a later
    turn didn't re-mention it; do let a later turn override to resolve or
    conflict."""
    if new.status == IntentStatus.KNOWN:
        return new
    if prev is not None and prev.status == IntentStatus.KNOWN:
        if new.status == IntentStatus.UNKNOWN:
            return prev
        return new  # ambiguous/conflicting explicitly raised this turn
    return new


def _merge_preferences(prev: list[Preference], new: list[Preference]) -> list[Preference]:
    merged = {p.category: p for p in prev if p.category}
    unnamed = [p for p in prev if not p.category]
    for p in new:
        if p.category:
            merged[p.category] = p
        else:
            unnamed.append(p)
    return list(merged.values()) + unnamed


def _merge_constraints(prev: Constraints, new: Constraints) -> Constraints:
    return Constraints(
        walking_limit_km=new.walking_limit_km if new.walking_limit_km is not None else prev.walking_limit_km,
        budget_per_day_usd=new.budget_per_day_usd if new.budget_per_day_usd is not None else prev.budget_per_day_usd,
        must_visit=new.must_visit or prev.must_visit,
        avoid=new.avoid or prev.avoid,
    )


def build_structured_intent(
    draft: dict,
    prev_intent: StructuredIntent | None,
    turn: int,
    chat_on: bool,
) -> StructuredIntent:
    """
    Build a StructuredIntent from the LLM draft.

    chat_on=False:
        - Single-turn extraction.
        - No merging with previous intent.
        - No turn-cap fallback.

    chat_on=True:
        - Merge with previous intent.
        - Enable clarification workflow.
    """

    if chat_on:
        fields = {
            f: _merge_field(
                getattr(prev_intent, f) if prev_intent else None,
                _cast_field(f, draft.get(f)),
            )
            for f in ALL_FIELDS
        }

        preferences = _merge_preferences(
            prev_intent.preferences if prev_intent else [],
            _cast_preferences(draft.get("preferences")),
        )

        constraints = _merge_constraints(
            prev_intent.constraints if prev_intent else Constraints(),
            _cast_constraints(draft.get("constraints")),
        )

    else:
        fields = {
            f: _cast_field(f, draft.get(f))
            for f in ALL_FIELDS
        }

        preferences = _cast_preferences(
            draft.get("preferences")
        )

        constraints = _cast_constraints(
            draft.get("constraints")
        )

    clarification_question = _cast_clarifications(
        draft.get("clarification_question")
    )


    intent = StructuredIntent(
        **fields,
        preferences=preferences,
        constraints=constraints,
        clarification_question=clarification_question,
    )

    return _evaluate(intent, turn, chat_on)

def _evaluate(
    intent: StructuredIntent,
    turn: int,
    chat_on: bool,
) -> StructuredIntent:

    missing_required = [
        f
        for f in REQUIRED_FIELDS
        if getattr(intent, f).status == IntentStatus.UNKNOWN
    ]

    ambiguities = [
        f
        for f in ALL_FIELDS
        if getattr(intent, f).status in (
            IntentStatus.AMBIGUOUS,
            IntentStatus.CONFLICTING,
        )
    ]

    # Turn-cap fallback only exists during chat mode
    if chat_on and turn >= MAX_TURNS and (missing_required or ambiguities):
        for f in list(missing_required):
            if f in FALLBACK_DEFAULTS:
                setattr(
                    intent,
                    f,
                    FieldState(
                        value=FALLBACK_DEFAULTS[f],
                        status=IntentStatus.KNOWN,
                        evidence="auto-defaulted after max clarification turns",
                    ),
                )

        missing_required = [
            f
            for f in REQUIRED_FIELDS
            if getattr(intent, f).status == IntentStatus.UNKNOWN
        ]

        ambiguities = [
            f
            for f in ALL_FIELDS
            if getattr(intent, f).status in (
                IntentStatus.AMBIGUOUS,
                IntentStatus.CONFLICTING,
            )
        ]

    # intent.missing_required = missing_required # shifted to ExtractionResult
    intent.ambiguities = ambiguities

    if chat_on:
        intent.ready_for_planning = (
            (not missing_required and not ambiguities)
            or turn >= MAX_TURNS
        )
    else:
        intent.ready_for_planning = (
            not missing_required and not ambiguities
        )

    return intent