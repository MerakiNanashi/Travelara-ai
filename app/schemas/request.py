from pydantic import BaseModel, Field

# ─── Input / Planning Request ─────────────────────────────────────────────────

class PlanningRequest(BaseModel):
    """Raw natural-language trip request from the user."""
    query: str = Field(..., description="Natural language trip description")