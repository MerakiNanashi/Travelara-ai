# utils/run.py

from uuid import uuid4


# seed_runs.py

SEED_RUNS = {
    "9fb47fae-1f25-42b6-8462-c7ee39c6d699": "5-day Tokyo trip, interested in museums and food, medium budget, staying near Shinjuku",
    "f2d1d25c-7d8d-4b0e-8d8d-2d8c4d6b5a11": "3-day Paris itinerary focused on art museums, cafés, and walking tours",
    "7e9b6a41-1b64-4f85-b7d4-4f7d3ef5a209": "7-day Japan trip covering Tokyo, Kyoto, and Osaka with a JR Pass",
    "3b8b7f94-51f0-4b9c-bfe4-dbbf8f6d91e8": "4-day Singapore family trip with kids, attractions, and hawker centres",
    "a5e72cf9-2e83-4d0f-a7e7-4e45c5d7c3b2": "2-day Amsterdam trip prioritizing canals, museums, and local food",
    "c92d3ef6-13d7-4713-8d86-c8ef6d87f943": "6-day Bali itinerary with beaches, waterfalls, temples, and cafés",
    "16b4f1f7-9ef8-4c8a-91e5-86cf42cb7b31": "5-day London trip covering history, theatres, and British cuisine",
    "e4acbc78-6452-4bc7-9355-7c67a3d6f98e": "3-day New York City trip focused on landmarks, Broadway, and food",
    "8fd4c2e0-98d1-49c3-92c6-92f0c8dd94ab": "4-day Rome itinerary with ancient history, Vatican, and authentic Italian restaurants",
    "b1d39b27-4e58-42e9-9df3-1d91a8e5fc61": "5-day Seoul itinerary for K-pop, street food, palaces, and shopping",
}

def create_run_id(seed_num: int | None = None) -> str:

    if seed_num is not None:
        return list(SEED_RUNS.keys())[seed_num]
    return str(uuid4())