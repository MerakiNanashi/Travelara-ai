# extractor.py
# from config import 
from schema import UserInput, StructuredUserInput, Itinerary_Structure, DayStructure, ActivitySlot
from extractor import extract_itinerary_structure
from retreiver import retreive_poi


def main():
    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
        "I'm quite flexible with my plans and open to suggestions, but I do want to make sure I hit some key landmarks and try the local cuisine."
        "I also prefer to have a mix of activities each day, like visiting museums in the morning and exploring local markets or cafes in the afternoon."
        "Don't want to spend too much time traveling between locations, so ideally, activities should be clustered by area."
        "Don't want to spend all the time on touristy spots; would love to discover some hidden gems and local favorites as well."
        "I can handle a moderately busy schedule. I don't mind having some free time, but I also want to make the most of my trip and see as much as possible without feeling rushed."
    )

    structured_input = extract_itinerary_structure(input_text)
    print("Structured Input:")
    print(structured_input)

    poi_results = retreive_poi(structured_input)
    print("\nRetrieved POIs:")
    print(poi_results)

    