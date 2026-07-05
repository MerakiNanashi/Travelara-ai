from pydantic import BaseModel
from typing import Optional
from app.schemas.schema import Itinerary

class PlanResponse(BaseModel):
    success: bool
    itinerary: Optional[Itinerary] = None
    error: Optional[str] = None
