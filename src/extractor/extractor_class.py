from __future__ import annotations

import json
from pydantic import BaseModel
from abc import ABC

from src.shared.schemas import (
    IntentStatus,
    StructuredIntent,
    _ExtractorConfig,
    FieldState,
    Preference,
    Constraints
)
from src.shared.connections.gemini import single_call_gemini
from .prompt import build_prompt


class Extractor(ABC):

    def __init__(self,
                 config: _ExtractorConfig,
                 api_key: str,
                 schema: type[BaseModel]):
        
        self.api_key = api_key
        self.schema = schema
        self.prompt_version = config['prompt_version']
        self.temperature = config['temperature']
        self.max_turns = config['max_turns']
        self.active_model = config['active_model']
        self.fallback_model = config['fallback_model']
        self.url = config['url']
        self.timeout = config['timeout']
        self.thinking_level = config['thinking_level']

        self.top_level_fields = list(self.schema.model_fields.keys())
        self.non_field_fields = ["preferences", "constraints", "ready_for_planning"]

    def _extract_text(self, data: dict) -> str:
        try:
            for step in data.get("steps", []):
                if step.get("type") != "model_output":
                    continue
                for item in step.get("content", []):
                    if item.get("type") == "text":
                        return item["text"]
        except Exception as e:
            raise e
        
    def _load_json(self, raw_text: str) -> dict:
        if not raw_text or not raw_text.strip():
            raise

        text = raw_text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except:
            raise

        return data
    
    def _parse_field(self, field_name: str, raw: dict) -> FieldState:
        try:
            status = IntentStatus(raw.get("status")) or IntentStatus.UNKNOWN
            value = raw.get("value")
            evidence = raw.get("evidence") if isinstance(raw.get("evidence"), str) else ""

            if value is None or status == IntentStatus.UNKNOWN:
                return FieldState(value=None, status=status, evidence=evidence)
            
            return FieldState(value=value, status=status, evidence=evidence)
        except:
            raise

    def _parse_res(self, data: dict) -> StructuredIntent:
        fields = {}

        for name in self.schema.model_fields:
            if name in self.non_field_fields:
                continue

            fields[name] = self._parse_field(name, data.get(name))

        return StructuredIntent(
            **fields,
            preferences=[
                Preference.model_validate(p)
                for p in data.get("preferences", [])
            ],
            constraints=Constraints.model_validate(
                data.get("constraints", {})
            ),
            ready_for_planning=data.get("ready_for_planning"),
        )


    async def extract_intent(self, user_query: str) -> StructuredIntent:
        try:
            prompt = build_prompt(user_query=user_query)
            res_dict = await single_call_gemini(
                api_key=self.api_key, 
                prompt=prompt, 
                model=self.active_model,
                timeout=self.timeout,
                temp=self.temperature, 
                url=self.url, 
                schema=self.schema,
                thinking_level=self.thinking_level)
            
            res_str = self._extract_text(res_dict)
            res = self._load_json(res_str)
            StructuredIntent.model_validate(res)

            parsed_res = self._parse_res(res)
            return parsed_res
        
        except Exception as e:
            raise
        