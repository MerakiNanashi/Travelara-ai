from pydantic_settings import BaseSettings, SettingsConfigDict

latlon_path = r'' # fill in the path for cities500.txt data

class Settings(BaseSettings):
    gemini_api_key: str = ""
    geoapify_api_key: str = ""
    foursquare_api_key: str = ""

    # Planning defaults
    knn_k: int = 10
    max_anchors: int = 6
    beam_width: int = 3
    anchor_radius_km: float = 2.0
    refinement_iterations: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()