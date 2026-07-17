from __future__ import annotations

from src.shared.schemas import (
    PlanningState,
    Stage,
    StageContext,
)

from .BaseStage import BaseStage
from src.planner.plan import candidate_pool_to_itinerary


class PlanStage(BaseStage):

    def __init__(
        self,
        context: StageContext,
    ):
        super().__init__(context=context)

        self.debugger = context.debugger

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        itinerary = candidate_pool_to_itinerary(
            candidate_pool=state.artifacts.candidate_selection,
            intent=state.intent,
        )

        state.itinerary = itinerary

        self.debugger.report(
            Stage.PLAN,
            {
                "days": len(itinerary.days),
                "anchors": len(itinerary.anchors),
                "stops": sum(
                    len(day.stops)
                    for day in itinerary.days
                ),
            },
        )

        self.debugger.save_stage(
            Stage.PLAN,
            7,
            state,
        )

        return state