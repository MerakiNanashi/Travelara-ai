from __future__ import annotations

from abc import ABC, abstractmethod

from src.shared.schemas import PlanningState, StageContext


class BaseStage(ABC):
    def __init__(self, context: StageContext):
        self.context = context

    @abstractmethod
    async def run(
        self,
        state: PlanningState,
    ) -> PlanningState:
        ...