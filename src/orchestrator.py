from __future__ import annotations

from fastapi import APIRouter
from pathlib import Path

from src.shared.config import get_config, Settings
from src.shared.utils import create_run_id, Debugger
from src.shared.schemas import (
    PlanningRequest, 
    PlanResponse, 
    PlanningState,
    PipelineMetadata,
    StageContext
)
from src.stages.ExtractorStage import ExtractorStage
from src.stages.RetrievalStage import RetrievalStage
from src.stages.PruningStage import PruningStage
from src.stages.EnrichmentStage import EnrichmentStage
from src.stages.RerankerStage import RerankerStage

router = APIRouter(prefix="/plan", tags=["Planning"])

@router.post("/")
async def plan_trip(request: PlanningRequest, 
                    user_id: int | None = None) -> PlanResponse:

    # Get settings & secrets
    settings = Settings()
    
    config_dict = get_config(settings.config_path)

    run_id = create_run_id()
    metadata = PipelineMetadata(run_id=run_id)

    debug_dir: Path = settings.save_dir / "runs" / f"{run_id}"
    debugger = Debugger(run_id=run_id, dir=debug_dir, enabled=True)

    # Intialize state
    state = PlanningState(request=request,
                          metadata=metadata)
    
    context = StageContext(
        config=config_dict,
        debugger=debugger,
        settings=settings,
    )
    pipeline = [
        ExtractorStage(context=context),
        RetrievalStage(context=context),
        PruningStage(context=context),
        EnrichmentStage(context=context),
        RerankerStage(context=context),
        # PlanStage(),
    ]

    for stage in pipeline:
        state = await stage.run(state)

    return PlanResponse(
        success=True,
        itinerary=state.itinerary,
    )


if __name__ == "__main__":
    from src.shared.schemas import PlanningRequest

    if __name__ == "__main__":
        import asyncio
        import sys

        query = (
            " ".join(sys.argv[1:])
            or "5-day Tokyo trip, interested in museums and food, medium budget, staying near Shinjuku"
        )

        request = PlanningRequest(
            query=query,
        )

        result = asyncio.run(plan_trip(request))
        print(result)  
