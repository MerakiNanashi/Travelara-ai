"""
extractor.py
────────────
Orchestration only. Converts natural language → StructuredIntent via
Gemini, across up to MAX_TURNS clarification turns.

Gemini is used ONLY for extraction — nothing here ranks, filters, or plans.

Per-turn context sent to the model is intentionally minimal: prior user
statements, the previous turn's extracted snapshot, and whatever's still
missing/unresolved. See prompt.build_prompt for the exact contents.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel
from abc import ABC, abstractmethod

from app.config import settings, model
from app.schemas.intent import StructuredIntent, ConversationContext, ExtractionResult
from . import prompt
from . import validator
from .validator import (
    MAX_TURNS,
    ExtractionError,
    ExtractionParseError,
    ExtractionSchemaError,
    ExtractionServiceError
)

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/interactions"

# ─────────────────────────── Gemini call ──────────────────────────────────
class Extractor(ABC):

    def __init__(
        self,
        schema: type[BaseModel],
        chat_on: bool = False,
    ):
        self.schema = schema
        self.chat_on = chat_on

    @staticmethod
    def _extract_text(data: dict) -> str:
        for step in data.get("steps", []):
            if step.get("type") != "model_output":
                continue

            for item in step.get("content", []):
                if item.get("type") == "text":
                    return item["text"]

        raise ExtractionSchemaError("No model output found.")


    async def _call_gemini(self, prompt_text: str) -> str:
        if not settings.gemini_api_key:
            raise ExtractionServiceError("GEMINI_API_KEY not configured")

        payload = {
            "model": "gemini-3.1-flash-lite",
            "input": prompt_text,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": self.schema.model_json_schema(),
            },
            "generation_config": {
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GEMINI_URL}?key={settings.gemini_api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            raise ExtractionServiceError(f"Gemini request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise ExtractionServiceError(
                f"Gemini returned {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.HTTPError as e:
            raise ExtractionServiceError(f"Gemini request failed: {e}") from e
        try:
            data = response.json()
            return self._extract_text(data)
        except (KeyError, IndexError) as e:
            raise ExtractionSchemaError(f"Unexpected Gemini response shape: {e}") from e

    async def _extract_intent(
        self,
        prompt_text: str,
        prev_intent: StructuredIntent | None,
        turn: int,
    ) -> StructuredIntent:
        try:
            raw = await self._call_gemini(prompt_text)
            draft = validator.parse_gemini_response(raw)
            return validator.build_structured_intent(
                draft,
                prev_intent=prev_intent,
                turn=turn,
                chat_on=self.chat_on
            )
        except Exception as e:
            raise e
        
    async def extractor(
            self,
            user_message: str,
            context: ConversationContext | None = None,) -> ExtractionResult:
        
        if self.chat_on:
            ctx = context or ConversationContext()

            ctx.user_statements.append(user_message.strip())
            ctx.turn += 1

            intent = await self._extract_intent(
                prompt_text=prompt.build_prompt(
                    ctx.user_statements,
                    ctx.prev_intent,
                    chat_on=self.chat_on
                ),
                prev_intent=ctx.prev_intent,
                turn=ctx.turn
            )
            ctx.prev_intent = intent
            ready = intent.ready_for_planning or ctx.turn >= MAX_TURNS

            
            return ExtractionResult(
                intent=intent,
                ready=ready,
                clarification_questions=(
                    [intent.clarification_question]
                    if not ready and intent.clarification_question.question
                    else []
                ),
                turn=ctx.turn,
                context=ctx,
            )

        else:
            intent = await self._extract_intent(
                prompt_text=prompt.build_prompt(
                    user_query=user_message,
                    chat_on=False,
                ),
                prev_intent=None,
                turn=1
            )
    
        return ExtractionResult(
            intent=intent,
            clarification_questions=[intent.clarification_question],
        )

if __name__ == "__main__":
    import asyncio

    async def main():
        user_message = "I want to go to Paris for 5 days, starting next Monday. I have a budget of $2000 and prefer cultural experiences."
        extractor = Extractor(StructuredIntent, False)
        result = await extractor.extractor(user_message)
        print(result.model_dump_json(indent=2))

    asyncio.run(main())