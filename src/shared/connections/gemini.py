from __future__ import annotations
from pydantic import BaseModel
import httpx

async def single_call_gemini(api_key: str,
                             prompt: str,
                             temp: float, 
                             url: str,
                             schema: type[BaseModel],
                             timeout: int,
                             model: str,
                             thinking_level: str):
    if not api_key:
        response = {}
        raise

    payload = {
        "model": model,
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema.model_json_schema(),
        },
        "generation_config": {
            "temperature": temp,
            "thinking_level": "minimal"
        },
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{url}?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

    except httpx.TimeoutException as e:
        data = {}
        raise 
    except httpx.HTTPStatusError as e:
        data = {}
        raise 
    except httpx.HTTPError as e:
        data = {}
        raise 

    data = response.json()
    return data