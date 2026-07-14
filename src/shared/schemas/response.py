from __future__ import annotations

from pydantic import BaseModel
from typing import Optional
from .itinerary import Itinerary

class PlanResponse(BaseModel):
    success: bool
    itinerary: Optional[Itinerary] = None
    error: Optional[str] = None
