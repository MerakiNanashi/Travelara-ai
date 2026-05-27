# llm_endpoints.py

from google import genai
import sys
from pathlib import Path 

# add project root to sys.path - resolved from hierarchial planner
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))


from helper.utils import measure_latency


# -----------------------------
# Gemini Endpoint
# -----------------------------
@measure_latency
def gemini_ep(api_key: str, prompt: str, config, schema) -> str:
    """
    Generate response using Google Gemini.
    """
    print("Starting Gemini Client...")
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=config['llm']['active_model'],
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": schema.model_json_schema(),
            "temperature": config['llm']['temperature'],
            "top_p": config['llm']['top_p']
        },
    )

    return response.text


# -----------------------------
# GPT Endpoint
# -----------------------------
def gpt_ep(api_key: str, prompt: str) -> str:
    """
    Generate response using OpenAI GPT.
    """
    pass


# -----------------------------
# Small Local Model Loader
# -----------------------------
def slm_load(model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"):
    """
    Load a small local HuggingFace model.
    """
    pass

# -----------------------------
# Example Usage
# -----------------------------
if __name__ == "__main__":
    from config.config import CONFIG_PATH, read_config, GEMINI_API_KEY, SERP_API_KEY, FS_API_KEY, YELP_FUSION_API_KEY
    from helper.schema import NormalizedInput

    config = read_config(CONFIG_PATH)

    print(config)

    gemini_response = gemini_ep(
        GEMINI_API_KEY,
        "Generate a 3-day itinerary for a trip to Paris, including must-see attractions, dining recommendations, and local tips.",
        config,
        NormalizedInput
    )

    print("Gemini Response:")
    print(gemini_response)
