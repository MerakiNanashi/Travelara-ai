from __future__ import annotations

from src.shared.schemas import StructuredIntent, PlanningState, Stage, StageContext
from .BaseStage import BaseStage
from src.extractor import Extractor

# state should be copied, updated and returned instead of in place updation
class ExtractorStage(BaseStage):
    
    def __init__(self, context: StageContext):
        super().__init__(
            context=context
        )
        self.debugger = context.debugger
        self.settings = context.settings
        self.config = context.config['stage1']
        self.schema = StructuredIntent
        self.api_key = self.settings.gemini_api_key

    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:

        extractor = Extractor(config=self.config,
                              api_key=self.api_key,
                              schema=self.schema)
        raw_res, result = await extractor.extract_intent(
            user_query=state.request.query,
        )

        state.intent = result

        self.debugger.report('raw_res', raw_res)
        self.debugger.save_stage(Stage.INTENT, 1, state)
 
        return state
    
