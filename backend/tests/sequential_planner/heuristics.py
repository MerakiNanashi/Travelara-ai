# VERSION 2: DAILY ENVELOPE APPROACH

# To do: hybrid approach with slot-level adjustments based on preferences/constraints (Eg. if user has "low crowd" constraint, we can allocate more budget to a usually crowded attraction but suggest visiting during off-peak hours, etc.)
# To do: Can also experiment with a more dynamic approach where we first allocate a base budget to each slot and then adjust based on preferences/constraints iteratively.
# To do: use preference weights to adjust slot budgets (Eg. if a user highly prefers cultural activities, we can allocate more budget to museum slots even if they are marked as "low" budget, etc.)

from pprint import pprint


# -----------------------------
# CONFIG
# -----------------------------

BUDGET_WEIGHTS = {
    "free": 0.0,
    "low": 0.2,
    "medium": 0.5,
    "high": 1.0
}

CATEGORY_MULTIPLIERS = {
    "cafe": 0.7,
    "park": 0.3,
    "museum": 1.0,
    "landmark": 1.0,
    "restaurant": 1.2,
    "cultural": 1.1,
    "shopping": 1.8,
    "nightlife": 1.5,
    "entertainment": 1.6,
    "adventure": 2.0
}

VARIABILITY = {
    "free": 0.0,
    "low": 0.25,
    "medium": 0.35,
    "high": 0.50
}


# -----------------------------
# HELPERS
# -----------------------------

def slot_weight(slot):
    """
    Computes slot importance weight.
    """

    budget_weight = BUDGET_WEIGHTS.get(
        slot["budget"],
        0.5
    )

    category_multiplier = CATEGORY_MULTIPLIERS.get(
        slot["category"],
        1.0
    )

    return budget_weight * category_multiplier


def compute_day_weight(day):
    """
    Computes total weight for a day.
    """

    total = 0

    for slot in day["slots"]:
        total += slot_weight(slot)

    return total


def budget_range(expected, budget_level):
    """
    Creates min/max budget range.
    """

    variability = VARIABILITY.get(
        budget_level,
        0.35
    )

    return {
        "min": round(expected * (1 - variability * 0.5), 2),
        "expected": round(expected, 2),
        "max": round(expected * (1 + variability), 2)
    }


# -----------------------------
# MAIN LOGIC
# -----------------------------

def allocate_daily_envelope(itinerary, total_budget):
    """
    Daily-envelope budgeting approach.

    1. Compute day weights
    2. Split total budget across days
    3. Split day budget across slots
    4. Generate ranges
    """

    days = itinerary["day_itinerary"]

    # STEP 1:
    # Compute day weights

    day_weights = []

    total_day_weight = 0

    for day in days:

        weight = compute_day_weight(day)

        day_weights.append(weight)

        total_day_weight += weight

    # STEP 2:
    # Allocate budgets to each day

    enriched_days = []

    for index, day in enumerate(days):

        current_day_weight = day_weights[index]

        day_budget = (
            total_budget *
            (current_day_weight / total_day_weight)
        )

        # STEP 3:
        # Compute slot weights inside day

        total_slot_weight = 0

        slot_weights = []

        for slot in day["slots"]:

            weight = slot_weight(slot)

            slot_weights.append(weight)

            total_slot_weight += weight

        enriched_slots = []

        # STEP 4:
        # Allocate slot budgets

        for slot_index, slot in enumerate(day["slots"]):

            current_slot_weight = slot_weights[slot_index]

            # Free activities
            if total_slot_weight == 0:
                expected = 0
            else:
                expected = (
                    day_budget *
                    (current_slot_weight / total_slot_weight)
                )

            slot_result = {
                "category": slot["category"],
                "budget_level": slot["budget"],
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "budget_range": budget_range(
                    expected,
                    slot["budget"]
                )
            }

            enriched_slots.append(slot_result)

        enriched_days.append({
            "day_number": day["day_number"],
            "day_budget": round(day_budget, 2),
            "slots": enriched_slots
        })

    return enriched_days

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    itinerary = {
        "day_itinerary": [
            {
                "day_number": 1,
                "slots": [
                    {
                        "category": "restaurant",
                        "budget": "medium",
                        "start_time": "12:00",
                        "end_time": "13:30",
                        "tags": ["local cuisine"]
                    },
                    {
                        "category": "museum",
                        "budget": "low",
                        "start_time": "14:00",
                        "end_time": "16:00",
                        "tags": ["art", "history"]
                    }
                ]
            },
            {
                "day_number": 2,
                "slots": [
                    {
                        "category": "adventure",
                        "budget": "high",
                        "start_time": "09:00",
                        "end_time": "12:00",
                        "tags": ["outdoors", "thrill"]
                    },
                    {
                        "category": "cafe",
                        "budget": "low",
                        "start_time": "15:00",
                        "end_time": "16:00",
                        "tags": ["relaxing", "coffee"]
                    }
                ]
            }
        ]
    }


    TOTAL_BUDGET = 2000

    results = allocate_daily_envelope(
        itinerary,
        TOTAL_BUDGET
    )

    for r in results:
        print(r)