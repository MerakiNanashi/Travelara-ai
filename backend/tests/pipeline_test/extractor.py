from google import genai
from schema import UserInput, StructuredUserInput
from dotenv import load_dotenv
import json
import os
import time
from datetime import datetime
from helper import estimate_tokens, calculate_cost, measure_latency

# =========================
# CONFIG
# =========================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)


# =========================
# EXTRACTION PIPELINE
# =========================

@measure_latency
def extract_user_input(input_text) -> UserInput:

    prompt = f"""
    You are an information extraction system.

    Extract structured travel details from the user input.

    Return ONLY valid JSON. Do not include any explanation, thinking, or formatting outside JSON.

    Follow these rules:

    - source: starting location if mentioned, else null
    - destination: main place user wants to visit (string)
    - days: number of days (integer, default = 3 if not specified)
    - budget: total budget if mentioned, else null
    - international: true if destination is outside India, false if domestic.
    - preferences: list of concise interests
    - constraints: list of concise constraints (Eg. "Low crowd", "Wheelchair accessibility", "Low travel time", etc.)

    - Allowed categories (STRICT):
    tourist_attraction, restaurant, cafe, beach, shopping,
    nightlife, museum, park, landmark, entertainment, adventure, cultural

    - Itinerary Structure Rules:

            - Each day must contain activity slots according to the user's preferences and general travel patterns.
            - Ensure at least one preference-aligned slot per day
            - Always provide detailed reasoning for the structure in the "reasoning" field (Eg. why certain categories were chosen, how preferences were distributed, why the amount of activity slots, etc.)
            - Do not provide specific activity names, just the category and details for each slot.
            - Usual eating slots (restaurant/cafe) should be around typical meal times.
            - Tourist attractions and cultural sites are often visited in the morning or early afternoon.
            - Nightlife should be in the evening.
            - The structure should make logical sense (Eg. not having a beach slot in the middle of the day followed by a museum visit right after, etc.)

    - itinerary_structure:
        - Create a day-wise structure

        - Each slot must include:
            - category
            - mandatory
            - start_time
            - end_time
            - budget (range or estimate, eg. "free", "low", "medium", "high" or specific amount)
            - preference_weight (a float [0.0, 1.0] indicating how well this slot aligns with user preferences, to be used later in budgeting and itinerary optimization)
            - tags


    Input:
    {input_text}
    """

    # -------------------------
    # TOKEN ESTIMATION
    # -------------------------

    estimated_input_tokens = estimate_tokens(prompt)

    # -------------------------
    # GEMINI CALL
    # -------------------------

    api_start = time.perf_counter()

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": StructuredUserInput.model_json_schema(),
            "temperature": 0.1
        },
    )

    api_end = time.perf_counter()

    api_latency = round(api_end - api_start, 4)

    print(f"[API LATENCY] Gemini Call: {api_latency} sec")

    # -------------------------
    # RESPONSE PARSING
    # -------------------------

    data = json.loads(response.text)

    estimated_output_tokens = estimate_tokens(response.text)

    # -------------------------
    # COST CALCULATION
    # -------------------------

    cost_metrics = calculate_cost(
        estimated_input_tokens,
        estimated_output_tokens
    )

    print("\n[COST METRICS]")
    print(json.dumps(cost_metrics, indent=2))

    # -------------------------
    # OUTPUT DIRECTORY
    # -------------------------

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    dir_1 = "output"

    if not os.path.exists(dir_1):
        os.makedirs(dir_1)

    dir_2 = os.path.join(dir_1, "extracted_inputs")

    if not os.path.exists(dir_2):
        os.makedirs(dir_2)

    filename = f"extracted_{timestamp}.json"

    filepath = os.path.join(dir_2, filename)

    # -------------------------
    # SAVE OUTPUT
    # -------------------------

    final_output = {
        "metadata": {
            "timestamp": timestamp,
            "api_latency_sec": api_latency,
            "cost_metrics": cost_metrics
        },
        "data": data
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] {filepath}")

    return final_output


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
    )

    result = extract_user_input(input_text)

    print("\n[FINAL OUTPUT]")
    print(json.dumps(result, indent=2, ensure_ascii=False))