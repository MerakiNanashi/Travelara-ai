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

def _extract_text(data: dict) -> str:
    for step in data.get("steps", []):
        if step.get("type") != "model_output":
            continue

        for item in step.get("content", []):
            if item.get("type") == "text":
                return item["text"]

    raise ExtractionSchemaError("No model output found.")


async def _call_gemini(prompt_text: str) -> str:
    if not settings.gemini_api_key:
        raise ExtractionServiceError("GEMINI_API_KEY not configured")

    payload = {
        "model": "gemini-3.1-flash-lite",
        "input": prompt_text,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": StructuredIntent.model_json_schema(),
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

    data = response.json()
    print(data)
    try:
        return _extract_text(data)
    except (KeyError, IndexError) as e:
        raise ExtractionSchemaError(f"Unexpected Gemini response shape: {e}") from e

async def extract_intent(
        user_message: str,
        context: ConversationContext | None = None,
        chat_on: bool = False,) -> ExtractionResult:
    
    if chat_on:
        ctx = context or ConversationContext()

        if not user_message or not user_message.strip():
            raise ExtractionParseError("Empty user message.")

        ctx.user_statements.append(user_message.strip())
        ctx.turn += 1

        prompt_text = prompt.build_prompt(
            user_statements=ctx.user_statements,
            prev_intent=ctx.prev_intent,
            missing_required=ctx.prev_intent.missing_required if ctx.prev_intent else [],
            ambiguities=ctx.prev_intent.ambiguities if ctx.prev_intent else [],
            chat_on=chat_on
        )
        raw_text = await _call_gemini(prompt_text)
        draft = validator.parse_gemini_response(raw_text)
        print("draft", draft)
        intent = validator.build_structured_intent(draft, ctx.prev_intent, turn=ctx.turn, chat_on=chat_on)

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
        prompt_text = prompt.build_prompt(user_query=user_message, chat_on=chat_on)
        raw_text = await _call_gemini(prompt_text)
        print("Raw text from Gemini:", raw_text)
        draft = validator.parse_gemini_response(raw_text)
        intent = validator.build_structured_intent(draft, prev_intent=None, turn=1, chat_on=chat_on)
 
    return ExtractionResult(
        intent=intent,
        clarification_questions=[intent.clarification_question],
    )

if __name__ == "__main__":
    import asyncio

    async def main():
        user_message = "I want to go to Paris for 5 days, starting next Monday. I have a budget of $2000 and prefer cultural experiences."
        result = await extract_intent(user_message, chat_on=False)
        print(result.model_dump_json(indent=2))

    asyncio.run(main())