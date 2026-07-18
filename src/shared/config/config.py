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
    save_dir: Path = ROOT_DIR / "data"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        case_sensitive=False,
        extra="ignore",
    )


_PATH_KEYS = {
    "path",
    "gl_path",
    "dom_path",
    "taxonomy_path",
}


def _resolve_paths(obj, root: Path):
    if isinstance(obj, dict):
        resolved = {}
        for k, v in obj.items():
            if k in _PATH_KEYS and isinstance(v, str):
                p = Path(v)
                resolved[k] = str(p if p.is_absolute() else (root / p).resolve())
            else:
                resolved[k] = _resolve_paths(v, root)
        return resolved

    if isinstance(obj, list):
        return [_resolve_paths(v, root) for v in obj]

    return obj

settings = Settings()
def get_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return _resolve_paths(config, settings.root_dir)