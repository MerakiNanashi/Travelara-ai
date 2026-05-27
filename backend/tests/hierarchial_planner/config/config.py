from pathlib import Path
import os
import yaml
from dotenv import load_dotenv


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERP_API_KEY = os.getenv("SERP_API_KEY")
FS_API_KEY = os.getenv("FS_API_KEY")
YELP_FUSION_API_KEY = os.getenv("YELP_FUSION_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

# Working from base dir tests
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Working from parent dir hierarchial planner
PARENT_DIR = BASE_DIR / "hierarchial_planner"

CONFIG_PATH = PARENT_DIR / "config"/ "config.yaml"
DATA_DIR = PARENT_DIR / "data"
MODEL_DIR = PARENT_DIR / "model"
RESULT_DIR = PARENT_DIR / "results"
PROMPT_DIR = RESULT_DIR / "prompts"
POI_SAVE_DIR = RESULT_DIR / "poi_result"
EXTRACTOR_SAVE_DIR = RESULT_DIR / "extractor_result"

GEOLATLON_FILE = DATA_DIR / "latlon_index" / "cities500.txt"
IN_LATLON_FILE = DATA_DIR / "latlon_index" / "IN.txt"


dirs = {
    DATA_DIR,
    MODEL_DIR,
    RESULT_DIR,
    POI_SAVE_DIR,
    EXTRACTOR_SAVE_DIR,
    PROMPT_DIR,

}

for dir in dirs:
    os.makedirs(dir, exist_ok=True)


def read_config(config_path: str = CONFIG_PATH) -> dict:
    """
    Read YAML configuration file.
    """

    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        return config

    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return {}

    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}")
        return {}

__all__ = [
    "BASE_DIR",
    "PARENT_DIR",
    "CONFIG_PATH",
    "DATA_DIR",
    "MODEL_DIR",
    "RESULT_DIR",
    "POI_SAVE_DIR",
    "EXTRACTOR_SAVE_DIR",
    "PROMPT_DIR",
    "GEOLATLON_FILE",
    "IN_LATLON_FILE",
    "GEMINI_API_KEY",
    "SERP_API_KEY",
    "FS_API_KEY",
    "YELP_FUSION_API_KEY",
    "read_config",

]

if __name__ == "__main__":
    pass
