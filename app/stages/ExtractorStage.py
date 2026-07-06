from __future__ import annotations

from pydantic import BaseModel

from app.schemas import Stage, PlanningState
from app.extractor.extractor import Extractor


# state should be copied, updated and returned instead of in place updation
class ExtractorStage(Extractor):

    def __init__(self,):
        pass

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        result = await self.extractor(
            user_message=state.request.query,
        )

        state.intent = result.intent
        # state.conversation_context = result.context
        # state.ready_for_planning = result.ready
        # state.clarification_questions = result.clarification_questions

        return state