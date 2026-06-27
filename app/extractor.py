"""
Extractor service: converts natural language → StructuredIntent via Gemini 2.5 Flash Lite.
Gemini is used ONLY for extraction. All planning logic is deterministic.
"""
from __future__ import annotations
import json
import httpx
from app.schemas import StructuredIntent, Preferences, Constraints
from app.config import settings
import os


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"

SYSTEM_PROMPT = """You are a structured data extractor for a travel planning system.
Extract trip details from user input and return ONLY valid JSON matching this exact schema:

{
  "destination": "city name",
  "days": integer,
  "stay_location": "neighborhood or hotel area",
  "is_international": bool - True if destination is outisde India (non-domestic), else False
  "budget": "low" | "medium" | "high",
  "preferences": {
    "museums": 0.0-1.0,
    "food": 0.0-1.0,
    "nightlife": 0.0-1.0,
    "nature": 0.0-1.0,
    "shopping": 0.0-1.0,
    "arts": 0.0-1.0,
    "history": 0.0-1.0,
    "wellness": 0.0-1.0
  },
  "constraints": {
    "walking_limit_km": float (default 10),
    "must_visit": ["place names"],
    "avoid": ["categories to avoid"],
    "budget_per_day_usd": float or null
  },
  "start_date": "YYYY-MM-DD or null"
}

Rules:
- Infer preferences from context (e.g. "food lover" → food: 0.9)
- If user says "avoid excessive walking", set walking_limit_km to 5-6
- budget: "low" = hostels/street food, "medium" = mid-range, "high" = luxury
- Return ONLY JSON, no markdown, no explanation
"""


async def extract_intent(query: str) -> StructuredIntent:
    """Call Gemini 2.5 Flash Lite to extract structured planning intent."""

    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nUser input: {query}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1024,
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GEMINI_URL}?key={settings.gemini_api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    data = response.json()

    # Extract text from Gemini response
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    parsed = json.loads(text)

    return StructuredIntent(
        destination=parsed["destination"],
        days=int(parsed["days"]),
        stay_location=parsed.get("stay_location", parsed["destination"]),
        is_international=parsed.get("is_international", True),
        budget=parsed.get("budget", "medium"),
        preferences=Preferences(**parsed.get("preferences", {})),
        constraints=Constraints(**parsed.get("constraints", {})),
        start_date=parsed.get("start_date"),
    )
