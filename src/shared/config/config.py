from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    gemini_api_key: str = ""
    geoapify_api_key: str = ""
    foursquare_api_key: str = ""

    config_path: Path = BASE_DIR / "shared" / "config" / "config.yaml"
    root_dir: Path = ROOT_DIR
    base_dir: Path = BASE_DIR
    save_dir: Path = BASE_DIR / "data"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()


def get_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

