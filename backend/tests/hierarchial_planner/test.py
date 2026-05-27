import asyncio

from destination import retrieve_poi
from extractor.run_extractor import extractor


if __name__ == "__main__":
    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
    )

    _, state = extractor("i_1", "u_2", input_text)
    state, poi_results = asyncio.run(retrieve_poi(state, debug=True))

    print(state.model_dump_json(indent=2))
    print(f"Retrieved query groups: {len(poi_results)}")
