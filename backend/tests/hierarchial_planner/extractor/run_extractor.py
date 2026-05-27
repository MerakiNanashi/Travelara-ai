
import sys
from pathlib import Path 

# add project root to sys.path - resolved from hierarchial planner
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from extractor.prompt import prompt, save_prompt_version
from helper.llm_endpoints import gemini_ep
from helper.utils import measure_latency
from config.config import GEMINI_API_KEY, read_config
from helper.schema import NormalizedInput, GlobalState

@measure_latency
def extractor(i_id, u_id, user_input):
    config = read_config()
    i_id, u_id, prompt_text, final_prompt = prompt(i_id, u_id, user_input)
    save_prompt_version(prompt_text)
    response = gemini_ep(GEMINI_API_KEY, final_prompt, config, NormalizedInput)

    normalized_input = NormalizedInput.model_validate_json(response)
    global_state = GlobalState(
        i_id=i_id,
        u_id=u_id,
        normalizedinput=normalized_input,
        remaining_budget=normalized_input.budget,
    )

    # Should I resolve the lat/lon here itself?

    print("NormalizedInput:")
    print(normalized_input.model_dump_json(indent=2))
    print("\nGlobalState:")
    print(global_state.model_dump_json(indent=2))

    return normalized_input, global_state

if __name__ == '__main__':
    input_text = (
        "I want to visit Paris for 5 days with a budget of $2000. "
        "I love art, history, and food. "
        "I will be starting from London."
    )
    extractor('i_1', 'u_2', input_text)


