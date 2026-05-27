import hashlib
import sys
from pathlib import Path

# add project root to sys.path - resolved from hierarchial planner
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))


from config.config import PROMPT_DIR


PROMPT_VERSION = "1.0.0"


def prompt(i_id, u_id, user_input) -> str:
    prompt = f"""
You are an expert travel intent extraction and normalization engine.

Your task is to convert raw user travel requests into a strictly structured
`NormalizedInput` object.

You MUST:
1. Extract structured travel intent.
2. Preserve user intent accurately.
3. Generate meaningful semantic search queries.
4. Detect conflicting constraints/preferences.
5. Return ONLY valid JSON matching the schema.
6. Never include explanations, markdown, comments, or extra text.

-----------------------------------
FIELD EXTRACTION RULES
-----------------------------------

1. d_name: Destination Name [Required]
2. starting_point: Stay/starting point if given, None by default.
3. days: No. of days of the trip [Required]
4. is_international: True if destination is non-domestic (ie. Outside India), else False. [Required]
5. budget: Trip budget [Required]
6. max_travel_time_per_day: Max travel time per day according to user constraints/preferences. [Required]
7. min_unique_categories: Minimum optimal unique categories trip should include s.t user preferences/constraints
8. h_constraints: List of hard constraints (must follow) mentioned by user.
9. s_constraints: List of soft constraints (flexible) mentioned by user
    Rules:
    - Constraints must be normalized into short atomic concepts.
    - Split combined concepts into separate constraints.
    - Avoid conjunctions (and, &, /).
    - Prefer semantic categories over natural language sentences.
    - Use more specific normalized constraints ONLY when the user explicitly requires specificity.

    Structure for `h_constraints` & `s_constraints`:
    - c_id: unique constraint id
    - constraint: normalized constraint eg. Wheelchair, Museum, Specific Location, etc.
    - priority: [1, 0] -> Indicates the priority of the constraint
    - conflicting: True if any conflicting constraint, else False
    - c_list: list of conflicting constraint c_id 
    * Note: Conflicting refers to a constraint that clashes against the particular constraint

10. queries: List of normalized semantic anchor queries for retrieving major landmarks, focal POIs, and primary travel anchors according to user preferences and constraints.
    Queries should remain broad semantic retrieval anchors unless specificity is required by user intent.
    Structure:
    - c_id: related constraint id
    - q_id: unique query id
    - day_number: list[int]
    - query: normalized semantic anchor query

    Rules:
    - Queries are ONLY for anchor retreival.
    - Anchors include:
        - landmarks
        - museums
        - tourist attractions
        - etc.
    - Queries should be retrieval-friendly semantic categories.
    - Queries should NOT target filler POIs such as random cafes/restaurants unless explicitly central to user intent.
    - Queries must map back to at least one user preference or constraint through `c_id`.
    - Generate approximately `3 * days` total queries.
    - Multiple queries may map to the same day.
    - Queries may overlap across days.
    - Queries should maximize diversity while respecting user preferences.
    - Avoid duplicate or semantically identical queries.
    - Do not include city names, etc. unless specificity is required.

    SPECIFICITY RULE:
    Only generate highly specific queries when directly implied by user constraints.
    Overly specific queries should be avoided unless directly required by the user.
    Specific named entities reduce retrieval diversity and are considered lower quality outputs.

    QUERY SPECIFICITY HIERARCHY:
    Always prefer the highest valid abstraction level.

    Priority order:
    1. category
    2. district type
    3. attraction class
    4. named attraction (ONLY if explicitly required)

    QUERY ABSTRACTION RULE
    Queries should generalize the FORM of the attraction, NOT the underlying user intent.
    Correct abstraction:
    User intent:
    - anime
    Query:
    - "anime districts"

    NOT:
    - "tourist attractions"

    QUERY QUALITY HEURISTIC

    A high-quality query:
    1. clearly reflects a user preference,
    2. remains retrieval-friendly,
    3. avoids exact POIs,
    4. avoids generic catch-all tourism phrasing.

    Avoid queries that are:
    - overly broad ("tourist attractions")
    - overly narrow ("best ramen shops in Shibuya")

"""
    
    final_prompt = prompt + \
f'''
-----------------------------------
USER INPUT
-----------------------------------
{user_input}
'''
    return i_id, u_id, prompt, final_prompt


def prompt_versioning(prompt_text: str) -> str:
    """
    Generates deterministic hash for prompt text.
    """
    return hashlib.md5(
        prompt_text.strip().encode("utf-8")
    ).hexdigest()


def save_prompt_version(prompt_text: str) -> str:
    """
    Saves prompt automatically if content changes.
    """
    prompt_hash = prompt_versioning(prompt_text)

    prompt_file = PROMPT_DIR / f"{prompt_hash}_{PROMPT_VERSION}.txt"

    if not prompt_file.exists():
        prompt_file.write_text(
            prompt_text,
            encoding="utf-8"
        )

    return prompt_hash

if __name__ == '__main__':
    # usage
    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
    )
    i_d, u_d, PROMPT_TEXT, PROMPT  = prompt('i_1', 'u_1', input_text )
    # print(PROMPT)
    PROMPT_HASH = save_prompt_version(PROMPT_TEXT)

    print(PROMPT_HASH)