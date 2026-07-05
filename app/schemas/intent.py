from app.schemas.enums import PreferenceCategory, PreferenceType, PreferenceStatus, IntentStatus
from pydantic import BaseModel, Field
from typing import Any


# ---------- Preference ----------
class Preference(BaseModel):
    category: PreferenceCategory 
    name: str = ""
    type: PreferenceType | None = None
    weight: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Importance for downstream scoring."
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5
    )
    status: PreferenceStatus | None = None
    evidence: str = ""

# ---------- Constraints ----------
class Constraints(BaseModel):
    walking_limit_km: float = 0.0
    budget_per_day_usd: float = 0.0
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)

# ---------- Field State ----------
class FieldState(BaseModel):
    value: Any = None
    status: IntentStatus = IntentStatus.UNKNOWN
    evidence: str = ""
    required: bool = False

# ---------- Clarification ----------
class ClarificationQuestion(BaseModel):
    field: str = ""
    question: str = ""
    reason: str = ""
    priority: int = 1

# ---------- Intent ----------
class StructuredIntent(BaseModel):
    """
    Future Updates:
    1. Categorize user into new_user, active_user, recurring_user, etc.
    2. Any places visited before? / Level of hiddeness idk?
    """

    destination: FieldState
    days: FieldState
    start_date: FieldState
    stay_location: FieldState
    is_international: FieldState
    budget: FieldState
    preferences: list[Preference] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    ready_for_planning: bool = False
    ambiguities: list[str] = Field(default_factory=list)
    clarification_question: ClarificationQuestion = Field(default_factory=ClarificationQuestion)

class ConversationContext(BaseModel):
    """Carried by the caller (e.g. the API layer) across clarification
    turns. Deliberately thin — just the raw user statements and the last
    extracted snapshot, nothing about the Gemini call machinery itself.
    """
    user_statements: list[str] = Field(default_factory=list)
    prev_intent: StructuredIntent | None = None
    turn: int = 0

class ExtractionResult(BaseModel):
    intent: StructuredIntent
    ready: bool = True
    missing_required: list[str] | None = None
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    turn: int = 0
    missing_required: list[str] | None = None
    context: ConversationContext = Field(default_factory=ConversationContext)
