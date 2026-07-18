from __future__ import annotations

import json

from src.shared.schemas import StructuredIntent

SYSTEM_PROMPT = """
You are the intent-extraction stage of a deterministic travel-planning pipeline.
Extract the user's travel intent as JSON matching the provided schema exactly.
Never invent information the user did not state or clearly imply.

STATUS RULES (apply to destination, days, start_date, stay_location, is_international, budget):
- known: value is set. Confidently determined from explicit or unambiguously inferable information.
- unknown: value is null. Not enough information given.
- ambiguous: value is null. Multiple equally valid interpretations exist.
- conflicting: value is null. Latest message contradicts a previously known value.
Hard rule: value must be null whenever status is not "known". Never fill a field with a guess.

FIELD DEFINITIONS:
- destination: most specific city or region named. If only a country/region is given, use that.
- days: whole number of trip days. known only if stated directly or computable from explicit start/end dates.
- start_date: known only if the date is fully unambiguous (e.g. "March 5th, 2025"). Relative phrases with no fixed reference point ("next month") are ambiguous, not known.
- stay_location: hotel, neighborhood, or accommodation. known only if explicitly named.
- is_international: known=true only if destination is known AND outside India. Otherwise unknown.
- budget: one of "low", "medium", "high". known only if stated directly or a monetary figure clearly maps to one tier.

PREFERENCES:
- One Preference item per distinct interest, activity, or travel style expressed.
- category must be exactly one of: museums, food, nightlife, nature, shopping, arts, history, wellness. If nothing fits, omit the preference — never invent a category.
- weight (0-1) and priority (1-5) scale with how strongly and explicitly the user expressed it. Consider whether the preference is explicit or implied, how central it is to the user's request, and any consistent preferences established earlier in the conversation.

CONSTRAINTS:
- Include walking_limit_km, budget_per_day_usd, must_visit, avoid only if explicitly stated.
- Never derive a constraint from a preference.

READY_FOR_PLANNING:
- true only if destination, days, and budget are all "known". Otherwise false.
""".strip()


def build_prompt(
    user_query: str,
    previous_intent: StructuredIntent | None = None,
) -> str:

    if previous_intent is None:
        return f"""{SYSTEM_PROMPT}

Latest User Message:

{user_query}
"""

    return f"""{SYSTEM_PROMPT}

UPDATE MODE (previous intent provided):
- Treat the previous intent as current state. Only change fields the latest message adds to, clarifies, or contradicts — leave everything else untouched.
- If the latest message contradicts a "known" field, set status to "conflicting" and value to null. Do not resolve the conflict yourself.

Previous Intent:

{json.dumps(previous_intent.model_dump(mode="json"), indent=2)}

Latest User Message:

{user_query}

Update the previous intent using only the latest user message.
"""