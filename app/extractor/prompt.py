"""
prompt.py
─────────
Owns everything Gemini needs to know how to behave, and nothing else:
  - the system prompt, assembled from small named sections (name/desc/rules)
  - the Gemini `responseSchema` (OpenAPI-subset) that forces structured JSON out
  - a `build_prompt(...)` helper that folds in the minimal per-turn context

No parsing, no casting, no merging logic lives here — that's validator.py's job.
"""
from __future__ import annotations
import re
from app.schemas import PreferenceCategory, StructuredIntent, PreferenceType, PreferenceStatus, IntentStatus, FieldState

# ─────────────────────────── Field status vocabulary ─────────────────────── #

FIELD_STATUSES = ["known", "unknown", "ambiguous", "conflicting"]
PREFERENCE_STATUSES = ["explicit", "inferred", "clarification"]
PREFERENCE_TYPES = ["objective", "subjective"]
PREFERENCE_CATEGORIES = [c.value for c in PreferenceCategory]

# ─────────────────────────── Prompt sections ──────────────────────────────
# Each section is {name, desc, rules[]}. Rendered top to bottom into the
# final system prompt. Keeps the prompt auditable/editable field-by-field
# instead of one wall of prose.

SYSTEM_SECTION = {
    "name": "System",
    "desc":
        """
        You are the intent extraction module of a deterministic travel
        planning system. Update the structured intent using the
        latest user message.
        """,
    "rules":
        """
        Never invent facts.
        Modify only affected fields.
        Resolve uncertainty whenever possible.
        Generate clarification questions only for unresolved required
        fields.
        Never overwrite a more specific value with a less specific one.
        """
}

FIELD_SECTIONS = [
    {
        "name": "destination",
        "desc":
            """
            Primary destination city or well-known region. Use the most
            specific resolvable place mentioned by the user. If multiple
            destinations are mentioned without a clear primary, leave the
            field ambiguous. Never invent or assume a city from only a
            country name. Required field.
            """
    },
    {
        "name": "days",
        "desc":
            """
            Total trip duration in whole days. Accept only positive
            integers. For reasonable ranges (e.g. 4–5 days), use the
            upper bound. Leave unknown if duration cannot be determined. Required field.
            """
    },
    {
        "name": "start_date",
        "desc":
            """
            Calendar date the trip begins. Resolve only when the date can
            be deterministically interpreted from the conversation.
            Never guess missing years or reference dates. Leave vague
            temporal expressions ambiguous.
            """
    },
    {
        "name": "stay_location",
        "desc":
            """
            Hotel, accommodation, or neighborhood where the traveler will
            stay. Optional. Record only explicitly mentioned locations.
            Never substitute the destination itself.
            """
    },
    {
        "name": "is_international",
        "desc":
            """
            Boolean; True if the destination is outside India (False otherwise).
            Derive solely from the resolved destination. Leave unresolved
            if the destination itself is unresolved. Required field.
            """
    },
    {
        "name": "budget",
        "desc":
            """
            Overall budget tier. Must be exactly one of: low, medium,
            high. Infer only when the user's travel style clearly implies
            one of these categories; otherwise leave unresolved.
            """
    },
    {
        "name": "preferences",
        "desc":
            f"""
        User interests used for downstream retrieval and ranking.

        Preference.category:
        - Must be exactly one of:
        {", ".join(PREFERENCE_CATEGORIES)}

        Preference.type:
        - Must be exactly one of:
        {", ".join(PREFERENCE_TYPES)}

        Preference.status:
        - Must be exactly one of:
        ({", ".join(PREFERENCE_STATUSES)})

        Preference.name:
        - Short free-text label describing the specific preference.
        - Leave empty if category alone fully captures the preference.

        Preference.weight:
        - Floating-point number in [0,1] indicating relative importance.
        - Always return a weight for every preference, even if the user did not explicitly assign one.

        Preference.priority:
        - Integer in [1,5] indicating relative importance, where 1 is highest priority.

        Populate every required Preference field exactly as defined by the schema. Required field.
            """
    },
    {
        "name": "constraints",
        "desc":
            """
            Hard planning constraints including walking_limit_km,
            must_visit, avoid, and budget_per_day_usd. Populate only
            constraints explicitly stated by the user. Never infer
            must_visit or avoid. Infer walking_limit_km only when the
            user clearly expresses limited walking ability or preference.
            Do not fabricate numeric values.
            """
    },
]

RESOLUTION_SECTION = {
    "name": "IntentStatus",
    "desc":
        f"""
        Every field must be assigned exactly one state:
        ({", ".join(IntentStatus)})
        """,
    "rules":
        """
        known: explicitly stated or deterministically inferable.
        unknown: insufficient information.
        ambiguous: multiple plausible interpretations.
        conflicting: contradicts previously resolved information.

        Generate clarification questions only for unresolved required
        fields (destination, days, budget). One concise question per
        field. Do not ask unnecessary questions.
        """
}
OUTPUT_SECTION = {
    "name": "Output",
    "desc":
        """
        The provided JSON Schema is the sole definition of the output structure.
        If the prompt and schema appear to conflict, always follow the schema.
        Do not infer alternative field names or wrapper objects.
        """,
    "rules":
        """
        Output valid JSON only. Do not produce markdown, explanations,
        commentary, or additional text.

        Populate every required schema field exactly as defined. Never add
        extra keys or omit required ones.

        Never invent, assume, or hallucinate information. If a value
        cannot be determined, leave it unresolved using the appropriate
        status.

        Resolve fields whenever there is sufficient evidence; otherwise
        preserve their previous resolution state.
        """
}

ALL_SECTIONS = [
    SYSTEM_SECTION,
    *[
        {
            "name": f"Field: {f['name']}",
            "desc": f["desc"],
        }
        for f in FIELD_SECTIONS
    ],
    RESOLUTION_SECTION,
    OUTPUT_SECTION,
]

ALL_SECTIONS = [
    {
        k: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v
        for k, v in section.items()
    }
    for section in ALL_SECTIONS
]


def render_section(section: dict) -> str:
    parts = [
        f"## {section['name']}",
        f"- Description: {section['desc']}",
    ]

    if section.get("rules"):
        parts.append(f"- Rules: {section['rules']}")

    return "\n".join(parts)


SYSTEM_PROMPT = "\n\n".join(render_section(s) for s in ALL_SECTIONS)


# ─────────────────────────── Context assembly ─────────────────────────────


def _render_prev_snapshot(prev_intent) -> str:
    """Compact known/unresolved-only view of the previous LLM output.
    Deliberately terse — full evidence strings are dropped to save tokens,
    only value+status survive, since evidence was already used once to
    reach that status.
    """
    if prev_intent is None:
        return "(none — this is the first turn)"
    fields = ["destination", "days", "start_date", "stay_location",
              "is_international", "budget"]
    lines = []
    for f in fields:
        fs = getattr(prev_intent, f)
        lines.append(f"- {f}: value={fs.value!r} status={fs.status.value}")
    if prev_intent.preferences:
        prefs = ", ".join(
            f"{p.category.value if p.category else p.name}={p.weight}"
            for p in prev_intent.preferences
        )
        lines.append(f"- preferences: {prefs}")
    return "\n".join(lines)

def build_prompt(
    user_statements: list[str] | None = None,
    prev_intent: StructuredIntent | None = None,
    missing_required: list[str] | None = None,
    ambiguities: list[str] | None = None,
    user_query: str | None = None,
    chat_on: bool = False,
) -> str:
    """Assemble the full prompt sent to Gemini for one turn."""

    prompt = "\n\n".join(SYSTEM_PROMPT.split("\n\n"))  # drop the "System" section, it's already in SYSTEM_PROMPT

    if not chat_on:
        return prompt + "\n\nUser query:\n" + (user_query or "")

    context_lines = [
        "## Conversation context",
        "User statements so far (in order):",
        *[f'{i + 1}. "{s}"' for i, s in enumerate(user_statements or [])],
        "",
        "Previously extracted snapshot:",
        _render_prev_snapshot(prev_intent),
        "",
        f"Still missing (required): {missing_required or 'none'}",
        f"Still unresolved (ambiguous/conflicting): {ambiguities or 'none'}",
        "",
        "Update the snapshot using the most recent user statement above.",
    ]

    return prompt + "\n\n" + "\n".join(context_lines)

if __name__ == "__main__":
    prompt = build_prompt(
        user_statements=[
            "I want to go to Paris for 5 days.",
            "I prefer museums and local cuisine.",
            "My budget is medium.",
        ],
        missing_required=["stay_location"],
        ambiguities=[],
        user_query="Where should I stay in Paris?",
    )
    print(prompt)