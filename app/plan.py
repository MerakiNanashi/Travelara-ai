from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from datetime import datetime
from app.schemas import (
    PlanningRequest, PlanResponse, IntentResponse, POIListResponse
)
from app.extractor import extract_intent
from app.providers.provider import run_retrieval
from app.planner import build_itinerary

router = APIRouter(prefix="/plan", tags=["Planning"])


@router.post("/", response_model=PlanResponse, summary="Full planning pipeline")
async def plan_trip(request: PlanningRequest):
    """
    End-to-end trip planning:
    1. Extract structured intent from natural language
    2. Retrieve candidate POIs (Geoapify + Foursquare)
    3. Build optimized itinerary (graph + beam search + refinement)
    """

    try:
        intent = await extract_intent(request.query)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Intent extraction failed: {e}"
        )

    try:
        pois, lat, lon = await run_retrieval("GA", intent)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"POI retrieval failed: {e}"
        )

    if not pois:
        raise HTTPException(
            status_code=404,
            detail="No POIs found for this destination"
        )

    itinerary = build_itinerary(pois, intent)

    # ------------------------------------------------------------------
    # Save itinerary
    # ------------------------------------------------------------------

    save_dir = Path("data/generated_itineraries")
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = (
        f"{intent.destination.lower().replace(' ', '_')}"
        f"_{timestamp}.json"
    )

    filepath = save_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            itinerary.model_dump(),
            f,
            indent=2,
            ensure_ascii=False,
        )

    return PlanResponse(
        success=True,
        itinerary=itinerary,
    )

@router.post("/extract-intent", response_model=IntentResponse, summary="Extract structured intent only")
async def extract_intent_endpoint(request: PlanningRequest):
    """Extract and return structured planning intent from natural language (no POI retrieval)."""
    try:
        intent = await extract_intent(request.query)
        return IntentResponse(success=True, intent=intent)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/retrieve-pois", response_model=POIListResponse, summary="Retrieve POIs only")
async def retrieve_pois_endpoint(request: PlanningRequest):
    """Retrieve candidate POIs for a destination without full planning."""
    try:
        intent = await extract_intent(request.query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Intent extraction failed: {e}")

    try:
        pois, lat, lon = await run_retrieval(intent)
        return POIListResponse(success=True, pois=pois, total=len(pois))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
