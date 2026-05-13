# models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# For Chat Page
class UserInput(BaseModel):
    source: Optional[str] = None
    destination: str
    days: int 
    budget: Optional[float] = None
    preferences: List[str] = []
    constraints: List[str] = []

# For NLP/NLU extractor output and structured input to candidate generator

class ActivityCategory(str, Enum):
    tourist_attraction = "tourist_attraction"
    restaurant = "restaurant"
    cafe = "cafe"
    beach = "beach"
    shopping = "shopping"
    nightlife = "nightlife"
    museum = "museum"
    park = "park"
    landmark = "landmark"
    adventure = "adventure"
    cultural = "cultural"
    entertainment = "entertainment"


class StructuredUserInput(BaseModel):
    source: Optional[str] = None
    destination: str
    days: int 
    international: bool
    budget: Optional[float] = None
    preferences: List[str] = []
    constraints: List[str] = []
    itinerary_structure: Itinerary_Structure

class ActivitySlot(BaseModel):
    category: ActivityCategory  # e.g. "tourist_attraction", "restaurant"
    mandatory: bool = True
    start_time: str
    end_time: str
    budget: str
    preference_weight: float
    tags: Optional[List[str]] = None  # optional semantic hints (LLM-driven)

class DayStructure(BaseModel):
    day_number: int
    slots: List[ActivitySlot]

class Itinerary_Structure(BaseModel):
    day_itinerary: List[DayStructure]
    reasoning: str

    # optional global constraints (LLM can fill/adapt)
    max_travel_time_per_day: Optional[int] = 180  # minutes
    min_unique_categories: Optional[int] = 2

# SerpAPI response parsing and candidate generator features
class POI(BaseModel):
    place_id: str
    name: str
    category: Optional[str] = None
    lat: float
    lon: float
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    price_level: Optional[int] = None
    tags: List[str] = []

# Final itinerary representation after candidate generation and ranking
class Itinerary(BaseModel):
    days: List[List[POI]]  # day -> list of POIs

class ScoredItinerary(BaseModel):
    itinerary: Itinerary
    score: float
    features: Dict[str, Any] = Field(default_factory=dict)